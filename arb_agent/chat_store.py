"""
Disk-backed persistence for chat sessions.

One JSON file per HLD under .arb_chat_sessions/. The hld_id is the first 16
hex chars of SHA-256(filename + content) — stable across browser refreshes
and re-uploads of the same file.

Atomic writes (write-to-temp + os.replace) so a crash mid-save never leaves
a partial file behind. Corrupt or missing files return a fresh empty session
rather than raising.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import List

from .chat import ChatMessage, ChatSession


CHAT_DIR = Path(".arb_chat_sessions")

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ID + path helpers
# ---------------------------------------------------------------------------
def compute_hld_id(filename: str, content: str) -> str:
    """Stable 16-hex-char id from filename + content.

    Same HLD (identical filename + identical bytes) always produces the same
    id. Different filename OR different content produces a different id.
    """
    digest = hashlib.sha256()
    digest.update(filename.encode("utf-8"))
    digest.update(content.encode("utf-8"))
    return digest.hexdigest()[:16]


def session_path(hld_id: str) -> Path:
    """Path to the session file for ``hld_id``. Creates CHAT_DIR if missing."""
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    return CHAT_DIR / f"{hld_id}.json"


# ---------------------------------------------------------------------------
# Load / save / delete
# ---------------------------------------------------------------------------
def load_session(hld_id: str) -> ChatSession:
    """Load a session from disk.

    Returns a fresh empty ChatSession when:
      - the file does not exist
      - the file is empty
      - the JSON is malformed
      - the JSON's shape is unrecognised

    Logs a warning in the corruption cases.
    """
    path = session_path(hld_id)
    if not path.exists():
        return ChatSession(hld_id=hld_id)

    try:
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            _log.warning(
                "chat_store: session file %s was empty; returning fresh session",
                path,
            )
            return ChatSession(hld_id=hld_id)

        data = json.loads(raw)
        messages_raw = data.get("messages", [])
        messages: List[ChatMessage] = [
            ChatMessage(
                role=str(m.get("role", "")),
                content=str(m.get("content", "")),
                timestamp=str(m.get("timestamp", "")),
            )
            for m in messages_raw
            if isinstance(m, dict)
        ]
        # Preserve the hld_id stored in the file when it matches; otherwise
        # use the caller-supplied id (and warn) so stray files don't poison.
        file_hld_id = str(data.get("hld_id", hld_id)) or hld_id
        if file_hld_id != hld_id:
            _log.warning(
                "chat_store: session file %s has hld_id mismatch (file=%s, expected=%s); "
                "using expected id",
                path, file_hld_id, hld_id,
            )
        return ChatSession(hld_id=hld_id, messages=messages)
    except (json.JSONDecodeError, OSError, ValueError) as e:
        _log.warning(
            "chat_store: failed to load session %s (%s); returning fresh session",
            path, e,
        )
        return ChatSession(hld_id=hld_id)


def save_session(session: ChatSession) -> None:
    """Atomic write: serialise to JSON, write tmp, ``os.replace`` onto final."""
    path = session_path(session.hld_id)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    data = {
        "hld_id": session.hld_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
            }
            for m in session.messages
        ],
    }
    payload = json.dumps(data, ensure_ascii=False, indent=2)

    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, path)


def delete_session(hld_id: str) -> bool:
    """Delete the session file. Returns True if a file existed."""
    path = session_path(hld_id)
    if not path.exists():
        return False
    try:
        path.unlink()
        return True
    except OSError as e:
        _log.warning("chat_store: failed to delete %s: %s", path, e)
        return False
