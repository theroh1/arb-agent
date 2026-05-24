"""
Checker — orchestrates the LLM calls across all 10 standards.

For each standard:
  1. Build the prompt (standards.py + prompts.py)
  2. Call the AWS Bedrock Converse API (Qwen model)
  3. Parse the JSON response
  4. Collect findings

If the JSON parse fails, we retry once with a stricter instruction. If it
still fails, we record an error for that standard but continue with the rest.

This module is designed for streaming UI: a progress callback is invoked
before and after each standard so the Streamlit app can update a progress bar.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable, List, Optional

import boto3

from .models import Finding, StandardResult, ReviewResult
from .prompts import SYSTEM_PROMPT, build_standard_prompt
from .standards import STANDARDS, Standard


DEFAULT_MODEL = "qwen.qwen3-coder-480b-a35b-v1:0"
DEFAULT_REGION = "us-east-1"
MAX_TOKENS = 4096


ProgressCallback = Callable[[int, Standard, str], None]
# args: (index 0-based, standard, status: "start" | "done" | "error")


def build_client(region: Optional[str] = None):
    """Construct a Bedrock runtime client.

    Resolves region from the argument, then AWS_REGION / AWS_DEFAULT_REGION
    env vars, finally DEFAULT_REGION. Authentication uses the standard boto3
    credential chain (including AWS_BEARER_TOKEN_BEDROCK if set).

    Reused by chat.py so follow-up conversations call Bedrock the same way
    run_review does — same region resolution, same client construction.
    """
    region = (
        region
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or DEFAULT_REGION
    )
    return boto3.client("bedrock-runtime", region_name=region)


def run_review(
    hld_text: str,
    hld_filename: str,
    region: Optional[str] = None,
    model: Optional[str] = None,
    progress: Optional[ProgressCallback] = None,
) -> ReviewResult:
    """Run all 10 standards against the HLD text and return the results.

    Authentication is handled by boto3 via the standard AWS credential chain.
    For Bedrock API keys, set AWS_BEARER_TOKEN_BEDROCK in the environment
    before this function runs.
    """
    model = model or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL)

    client = build_client(region)

    review = ReviewResult(hld_filename=hld_filename, model=model)

    for i, standard in enumerate(STANDARDS):
        if progress:
            progress(i, standard, "start")

        result = _evaluate_one_standard(client, model, standard, hld_text)
        review.results.append(result)

        if progress:
            progress(i, standard, "error" if result.error else "done")

    return review


def _evaluate_one_standard(
    client, model: str, standard: Standard, hld_text: str
) -> StandardResult:
    """Evaluate a single standard. One API call, with one retry on JSON failure."""
    result = StandardResult(standard=standard)
    prompt = build_standard_prompt(standard, hld_text)

    raw = None
    for attempt in (1, 2):
        try:
            response = client.converse(
                modelId=model,
                system=[{"text": SYSTEM_PROMPT}],
                messages=[
                    {"role": "user", "content": [{"text": prompt}]},
                ],
                inferenceConfig={
                    "maxTokens": MAX_TOKENS,
                    "temperature": 0.0,
                },
            )
            raw = _extract_text(response)
            result.raw_response = raw
            parsed = _parse_json_response(raw)
            result.findings = _build_findings(standard, parsed)
            return result
        except json.JSONDecodeError as e:
            if attempt == 2:
                result.error = f"JSON parse failed after retry: {e}. Raw output truncated: {(raw or '')[:300]}"
                return result
            # First failure: retry with stricter framing
            prompt = (
                "Your previous response was not valid JSON. Output ONLY valid JSON. "
                "Do not include markdown fences, commentary, or any text outside the JSON object.\n\n"
                + prompt
            )
        except Exception as e:
            result.error = f"Bedrock call failed: {type(e).__name__}: {e}"
            return result

    return result


def _extract_text(response) -> str:
    """Pull the text out of a Bedrock Converse response."""
    parts = []
    output = response.get("output", {})
    message = output.get("message", {})
    for block in message.get("content", []) or []:
        text = block.get("text")
        if text:
            parts.append(text)
    return "".join(parts).strip()


def _parse_json_response(text: str) -> dict:
    """Parse the LLM's JSON output, tolerating common formatting issues."""
    if not text:
        raise json.JSONDecodeError("Empty response", "", 0)

    # Strip markdown code fences if model added them despite instructions
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove opening fence (possibly ```json)
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        # Remove closing fence
        stripped = re.sub(r"\s*```\s*$", "", stripped)

    # Find the first { and last } to isolate the JSON object
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first == -1 or last == -1 or last < first:
        raise json.JSONDecodeError("No JSON object found", stripped, 0)
    candidate = stripped[first : last + 1]

    return json.loads(candidate)


def _build_findings(standard: Standard, parsed: dict) -> List[Finding]:
    """Validate and construct Finding objects from parsed JSON."""
    raw_findings = parsed.get("findings") or []
    if not isinstance(raw_findings, list):
        return []

    valid_check_ids = {c.id for c in standard.checks}
    out: List[Finding] = []

    for f in raw_findings:
        if not isinstance(f, dict):
            continue

        check_id = str(f.get("check_id", "")).strip()
        # Allow check IDs the standard didn't define, but stamp them clearly
        check_name = str(f.get("check_name", "")).strip() or "Unspecified check"
        severity = _normalise_severity(str(f.get("severity", "")).strip())
        if severity is None:
            continue  # invalid severity → skip

        finding = Finding(
            standard_id=standard.id,
            standard_name=standard.name,
            check_id=check_id if check_id in valid_check_ids else (check_id or "—"),
            check_name=check_name,
            severity=severity,
            evidence_section=str(f.get("evidence_section", "")).strip() or "—",
            evidence_quote=str(f.get("evidence_quote", "")).strip() or "—",
            issue=str(f.get("issue", "")).strip() or "—",
            authority=str(f.get("authority", "")).strip() or "—",
            recommendation=str(f.get("recommendation", "")).strip() or "—",
        )
        out.append(finding)

    # Sort by severity (High → Medium → Low) then by check_id
    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    out.sort(key=lambda x: (severity_order.get(x.severity, 99), x.check_id))
    return out


def _normalise_severity(s: str) -> Optional[str]:
    if not s:
        return None
    lower = s.lower()
    if lower.startswith("h"):
        return "High"
    if lower.startswith("m"):
        return "Medium"
    if lower.startswith("l"):
        return "Low"
    return None
