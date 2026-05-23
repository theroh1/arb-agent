"""
Prompt construction.

The agent's quality depends on these prompts. Three principles:

1. EVIDENCE OR NOTHING — every finding must cite a specific HLD section/quote.
   If there's no evidence, the agent must not invent a finding.
2. AUTHORITY CITATION — every finding cites which standard authority backs it.
   "I think this is bad" is not allowed; "AWS REL05 requires X" is.
3. STRICT JSON — output is machine-parseable. No prose, no preamble.

We use one prompt per standard. The LLM gets the standard definition, the
full HLD, and clear output rules.
"""
from __future__ import annotations

from .standards import Standard


SYSTEM_PROMPT = """You are an Architecture Review pre-screening agent. Your job is to assess a High-Level Design (HLD) document against universal architectural standards and produce defensible, evidence-based findings.

You are NOT a decision-maker. You do not approve or reject designs. You surface concerns for the Architecture Advisory Group (AAG) to evaluate.

You operate by three absolute rules:

1. EVIDENCE OR NOTHING. Every finding you produce must cite a specific section of the HLD and a direct quote (or explicitly note that the relevant content is absent from the HLD). You do not invent findings. You do not speculate about what the architect might have meant.

2. AUTHORITY CITATION. Every finding must name the published authority that defines the concern (TOGAF, AWS Well-Architected, OWASP, ISO 25010, etc.). You are not offering opinions — you are flagging departures from established industry practice.

3. STRICT JSON OUTPUT. Your responses are consumed by another system. You output only valid JSON in the exact schema specified. No preamble, no markdown fences, no commentary.

You are conservative. You would rather miss a marginal issue than fabricate one. If the HLD does not contain enough information to judge a check, you say so — you do not assume."""


def build_standard_prompt(standard: Standard, hld_text: str) -> str:
    """Build the user prompt for evaluating one standard against the HLD."""

    authorities = "\n".join(f"  - {a}" for a in standard.authorities)
    checks_block = "\n".join(_format_check(c) for c in standard.checks)
    severity_block = "\n".join(
        f"  - {level}: {trigger}" for level, trigger in standard.severity_rules.items()
    )
    boundaries = "\n".join(f"  - {b}" for b in standard.boundaries)

    check_ids = ", ".join(c.id for c in standard.checks)

    return f"""# TASK

Evaluate the HLD below against Standard {standard.display_id} — {standard.name}.

## STANDARD PURPOSE

{standard.purpose}

## GROUNDED IN

{authorities}

## CHECKS TO PERFORM

You must consider each of the following checks. For each check, decide whether the HLD has an issue (and produce a finding), or whether the check is satisfied / not applicable (and produce nothing for that check).

{checks_block}

## SEVERITY CALIBRATION

{severity_block}

## BOUNDARIES — WHAT THIS STANDARD DOES NOT JUDGE

{boundaries}

## HOW TO REASON

1. Read the HLD carefully. Identify the sections relevant to this standard.
2. For each check listed above (IDs: {check_ids}), determine whether the HLD addresses it adequately.
3. Where the HLD has a gap, anti-pattern, contradiction, or missing rationale relative to the check, produce a finding.
4. Where the HLD addresses the check adequately, OR the check is not applicable to this design, produce NO finding for that check.
5. For every finding, locate the specific section of the HLD as evidence. If the issue is the ABSENCE of required content, name the section where you would expect to find it (e.g., "Section 12 (Operational Impacts) - no content").

## OUTPUT FORMAT

Output a single JSON object. No markdown, no preamble, no trailing text.

Schema:

{{
  "standard_id": {standard.id},
  "standard_name": "{standard.name}",
  "findings": [
    {{
      "check_id": "string — must match one of the check IDs above",
      "check_name": "string — short name of the check",
      "severity": "High" | "Medium" | "Low",
      "evidence_section": "string — HLD section reference, e.g. 'Section 5.3' or 'Section 12 — absent'",
      "evidence_quote": "string — direct quote from the HLD, or 'No content found in the HLD addressing this concern'",
      "issue": "string — one to two sentences describing the gap or concern",
      "authority": "string — specific authority citation, e.g. 'AWS Well-Architected REL05-BP02' or 'GDPR Article 30'",
      "recommendation": "string — concrete action the architect can take to address the finding"
    }}
  ]
}}

If you find no issues, return:

{{
  "standard_id": {standard.id},
  "standard_name": "{standard.name}",
  "findings": []
}}

## HLD CONTENT

<<<HLD_BEGIN>>>
{hld_text}
<<<HLD_END>>>

Now produce the JSON. Output JSON only."""


def _format_check(c) -> str:
    return f"""  - {c.id} — {c.name}
    {c.description}"""
