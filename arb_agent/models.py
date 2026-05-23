"""
Data classes used across the agent.

These are deliberately free of any SDK imports so the reporter and Streamlit UI
can use them without pulling in anthropic, and so we can unit-test the agent's
output handling without making API calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .standards import Standard


@dataclass
class Finding:
    standard_id: int
    standard_name: str
    check_id: str
    check_name: str
    severity: str            # "High" | "Medium" | "Low"
    evidence_section: str
    evidence_quote: str
    issue: str
    authority: str
    recommendation: str


@dataclass
class StandardResult:
    standard: Standard
    findings: List[Finding] = field(default_factory=list)
    error: Optional[str] = None
    raw_response: Optional[str] = None


@dataclass
class ReviewResult:
    hld_filename: str
    model: str
    results: List[StandardResult] = field(default_factory=list)

    @property
    def total_findings(self) -> int:
        return sum(len(r.findings) for r in self.results)

    def findings_by_severity(self, severity: str) -> int:
        s = severity.lower()
        return sum(
            1
            for r in self.results
            for f in r.findings
            if f.severity.lower() == s
        )
