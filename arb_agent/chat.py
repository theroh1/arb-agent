"""
Chat module — follow-up Q&A on a completed ARB pre-review.

The chat reuses the same Bedrock client + Qwen model that produced the
findings. Each call builds a fresh system prompt embedding the full review
and the HLD text so the model has complete context for follow-ups.

Three absolute rules from the original review system prompt are preserved
here in chat form:
  1. Evidence or nothing — every architectural claim cites an HLD section
     and quote, or says explicitly that the HLD does not contain it.
  2. Authority citation — every architectural claim names its published
     authority (TOGAF, AWS WAF, OWASP, ISO, GDPR, etc.).
  3. Conservative posture — when uncertain, say so; do not invent.

The chat refuses to give verdicts and redirects off-topic questions back to
the HLD/findings scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .checker import build_client, DEFAULT_MODEL, MAX_TOKENS
from .models import Finding, ReviewResult, StandardResult


@dataclass
class ChatMessage:
    """A single message in a chat session."""

    role: str           # "user" | "assistant"
    content: str
    timestamp: str      # ISO 8601 string


@dataclass
class ChatSession:
    """A chat session, keyed by HLD."""

    hld_id: str
    messages: List[ChatMessage] = field(default_factory=list)


# ---------------------------------------------------------------------------
# System prompt construction
# ---------------------------------------------------------------------------
def build_chat_system_prompt(review: ReviewResult, hld_text: str) -> str:
    """Construct the system prompt for chat sessions.

    The prompt embeds the role, three absolute rules, all findings (formatted
    readably one block per finding), the full HLD text in delimiters, and the
    behavioural boundaries.
    """
    findings_block = _format_findings_block(review)

    return f"""You are an architecture governance assistant for an Architecture Advisory Group. You are answering follow-up questions about an HLD review you have already completed.

You operate by three absolute rules:

1. EVIDENCE OR NOTHING. Every architectural claim you make must cite a specific HLD section and a direct quote (or explicitly state "this is not in the HLD"). You do not invent HLD content. You do not speculate beyond what the document contains.

2. AUTHORITY CITATION. Every architectural claim must name its published authority (TOGAF, AWS Well-Architected, OWASP, ISO 25010, DAMA-DMBOK, GDPR, arc42, Enterprise Integration Patterns, etc.). You are not offering opinions — you are working from established industry practice.

3. CONSERVATIVE POSTURE. When you are uncertain, say so explicitly. Do not fabricate severity, do not invent findings beyond those produced in the review, do not speculate about what the architect "probably meant."

# BEHAVIOURAL BOUNDARIES

- You DECLINE to give verdicts. If asked "should I approve this design?" or "is this a good design?", respond: "That's the AAG's call. I can surface the gaps and authorities; the board decides." Then offer to summarise the highest-severity findings instead.

- You REDIRECT off-topic questions. If asked about anything outside this HLD and these findings (weather, news, general coding help, your own nature, etc.), respond briefly that you only answer questions about this HLD and its findings, and offer one concrete starter question.

- You PROPOSE FIXES as drop-in replacement text. When the user asks you to draft revised wording for a section, return it inside a markdown code block (```text … ```) so they can copy-paste it directly into their HLD. Pair the fix with the finding ID(s) it addresses.

# TONE

Precise, board-ready, concise. No filler phrases ("Great question", "Certainly!"). No marketing language. Default to short answers; expand only when the question demands it.

# REVIEW CONTEXT — FINDINGS PRODUCED

The review of `{review.hld_filename}` (model: {review.model}) produced {review.total_findings} findings across 10 standards:

{findings_block}

# REVIEW CONTEXT — HLD TEXT

The full text of the HLD follows. Use direct quotes from this text to ground every architectural claim. If a question can be answered only by reading content the HLD does not contain, say so.

<<<HLD_BEGIN>>>
{hld_text}
<<<HLD_END>>>

Now answer the user's question."""


def _format_findings_block(review: ReviewResult) -> str:
    """Render all findings as readable blocks (one block per finding)."""
    if review.total_findings == 0:
        return "_No findings were produced. The HLD passed all 59 checks._"

    blocks: List[str] = []
    for r in review.results:
        if r.error:
            blocks.append(
                f"## Standard {r.standard.display_id} — {r.standard.name}\n"
                f"_Standard could not be evaluated: {r.error}_\n"
            )
            continue
        if not r.findings:
            continue

        for idx, f in enumerate(r.findings, start=1):
            finding_id = f"F-{r.standard.display_id}.{idx}"
            blocks.append(_format_one_finding(finding_id, f))

    return "\n".join(blocks).strip()


def _format_one_finding(finding_id: str, f: Finding) -> str:
    """One finding block for the system prompt."""
    return (
        f"### {finding_id} · {f.severity.upper()} · {f.standard_name} ({f.check_id} {f.check_name})\n"
        f"- **Evidence section:** {f.evidence_section}\n"
        f"- **Evidence quote:** {f.evidence_quote}\n"
        f"- **Issue:** {f.issue}\n"
        f"- **Authority:** {f.authority}\n"
        f"- **Recommendation:** {f.recommendation}\n"
    )


# ---------------------------------------------------------------------------
# Message sending
# ---------------------------------------------------------------------------
def send_chat_message(
    session: ChatSession,
    user_message: str,
    review: ReviewResult,
    hld_text: str,
    api_key: Optional[str] = None,  # accepted for interface symmetry; boto3 uses env
    model: Optional[str] = None,
) -> ChatMessage:
    """Send a user message and return the assistant's reply.

    Appends BOTH the user message AND the assistant reply (or an error
    message) to ``session.messages`` before returning. Never raises.

    The ``api_key`` argument is part of the interface contract but not used
    directly — Bedrock auth comes from the env var ``AWS_BEARER_TOKEN_BEDROCK``
    (or the standard AWS credential chain) which boto3 reads at client
    construction time.
    """
    import os

    # Always record the user turn first, so it's visible even if the call fails.
    user_turn = ChatMessage(
        role="user",
        content=user_message,
        timestamp=_now_iso(),
    )
    session.messages.append(user_turn)

    model = model or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL)
    system_prompt = build_chat_system_prompt(review, hld_text)

    # Bedrock Converse expects strictly alternating user/assistant turns.
    # The session already alternates; we just translate to Bedrock's format.
    bedrock_messages = [
        {"role": m.role, "content": [{"text": m.content}]}
        for m in session.messages
    ]

    try:
        client = build_client()
        response = client.converse(
            modelId=model,
            system=[{"text": system_prompt}],
            messages=bedrock_messages,
            inferenceConfig={
                "maxTokens": MAX_TOKENS,
                "temperature": 0.2,
            },
        )
        reply_text = _extract_text(response)
        if not reply_text:
            reply_text = (
                "The model returned an empty response. "
                "Please try rephrasing the question."
            )
        assistant_turn = ChatMessage(
            role="assistant",
            content=reply_text,
            timestamp=_now_iso(),
        )
    except Exception as e:
        assistant_turn = ChatMessage(
            role="assistant",
            content=(
                f"_The chat agent could not reach Bedrock._\n\n"
                f"**Error:** `{type(e).__name__}: {e}`\n\n"
                f"Common causes: network interruption, the Bedrock API key has "
                f"expired or been rotated, or the model is not enabled in this "
                f"region. The conversation history above is preserved — try "
                f"the question again once the issue is resolved."
            ),
            timestamp=_now_iso(),
        )

    session.messages.append(assistant_turn)
    return assistant_turn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_text(response) -> str:
    """Pull the text out of a Bedrock Converse response."""
    parts: List[str] = []
    output = response.get("output", {})
    message = output.get("message", {})
    for block in message.get("content", []) or []:
        text = block.get("text")
        if text:
            parts.append(text)
    return "".join(parts).strip()


def _now_iso() -> str:
    """UTC ISO 8601 timestamp (seconds precision)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
