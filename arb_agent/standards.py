"""
The ten universal architectural standards.

Each standard defines:
- Purpose: what the standard is about
- Authorities: citable sources that ground each finding
- Checks: specific things the agent looks for in the HLD
- Severity calibration: rules for High/Medium/Low classification
- Boundaries: what the standard deliberately does NOT do

This data drives the prompts and the report structure.
"""
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class Check:
    id: str           # e.g. "1.A"
    name: str         # e.g. "Distributed monolith"
    description: str  # What the agent looks for


@dataclass
class Standard:
    id: int
    name: str
    purpose: str
    authorities: List[str]
    checks: List[Check]
    severity_rules: Dict[str, str]   # "High" / "Medium" / "Low" -> trigger description
    boundaries: List[str] = field(default_factory=list)

    @property
    def display_id(self) -> str:
        return f"{self.id:02d}"


STANDARDS: List[Standard] = [
    # ====================================================================
    Standard(
        id=1,
        name="Architecture Pattern Soundness",
        purpose=(
            "Surface structural anti-patterns — design choices with well-documented industry "
            "consensus as harmful. Flag only anti-patterns with established consensus, not "
            "stylistic preferences."
        ),
        authorities=[
            "Martin Fowler — Microservices and related architectural writing",
            "vFunction — Architectural anti-patterns research",
            "AWS Well-Architected Reliability Pillar (REL05)",
            "arc42 §5 (Building Block View)",
        ],
        checks=[
            Check("1.A", "Distributed monolith",
                  "Multiple services described as independent but tightly coupled at "
                  "deployment, data, or release. Services that must always release together."),
            Check("1.B", "Shared database between services",
                  "Two or more services writing to the same database tables, eliminating the "
                  "boundary that makes services independent."),
            Check("1.C", "Synchronous chain on critical path",
                  "Three or more synchronous service calls in sequence on a user-facing path "
                  "with no resilience pattern (timeout, circuit breaker, fallback)."),
            Check("1.D", "God component",
                  "One component owning a disproportionate share of business logic, with many "
                  "systems depending on it."),
            Check("1.E", "Missing resilience pattern",
                  "External dependencies described without retry, timeout, circuit breaker, or "
                  "fallback behaviour stated."),
        ],
        severity_rules={
            "High": "Clear anti-pattern on critical path with no mitigating control described.",
            "Medium": "Anti-pattern signals present but partial mitigation exists, or off critical path.",
            "Low": "Pattern at risk of becoming an anti-pattern; clarification recommended.",
        },
        boundaries=[
            "Does not judge whether the chosen pattern is 'right' for the use case.",
            "Does not flag patterns the architect has explicitly justified with a documented trade-off.",
        ],
    ),

    # ====================================================================
    Standard(
        id=2,
        name="Reliability & Failure Handling",
        purpose=(
            "Check that the design has accounted for failure modes and recovery, rather than "
            "assuming the happy path. Reliability is one of the most commonly under-specified "
            "concerns in HLDs because it is invisible until the first incident."
        ),
        authorities=[
            "AWS Well-Architected Reliability Pillar",
            "Azure Well-Architected Reliability Pillar",
            "ISO 22301 (Business Continuity Management)",
            "TOGAF Phase G — Implementation Governance",
        ],
        checks=[
            Check("2.A", "Single points of failure (SPOFs)",
                  "Any component on the critical path with no redundancy, failover, or "
                  "stateless replacement strategy described."),
            Check("2.B", "Failure mode coverage",
                  "For each external dependency, does the HLD describe what happens if it is "
                  "unavailable, slow, or returns errors?"),
            Check("2.C", "Recovery objectives — RTO / RPO",
                  "Are recovery time and recovery point objectives stated? Consistent with the "
                  "criticality of the workload?"),
            Check("2.D", "Rollback and change safety",
                  "Is there a rollback path for each change type (code, data, configuration)? "
                  "Are risky changes protected (feature flags, canary, blue-green)?"),
            Check("2.E", "Consistency under failure",
                  "What happens to in-flight transactions if a component fails mid-operation? "
                  "Is the consistency model stated?"),
            Check("2.F", "Cascade containment",
                  "Are failures contained at component boundaries (bulkheads, circuit breakers), "
                  "or can a single failure propagate?"),
        ],
        severity_rules={
            "High": "Critical-path SPOF with no failover described, or no recovery objectives for a stated-critical workload.",
            "Medium": "Recovery objectives stated but inconsistent; rollback missing for some change types.",
            "Low": "Specific failure mode not enumerated; clarification recommended.",
        },
        boundaries=[
            "Does not validate RTO/RPO values — those are business decisions.",
            "Does not run reliability tests on actual systems.",
        ],
    ),

    # ====================================================================
    Standard(
        id=3,
        name="Security Design Principles",
        purpose=(
            "Check that the design names the security controls expected for a system of this "
            "type. Not a penetration test — a check that security has been thought about at all."
        ),
        authorities=[
            "AWS Well-Architected Security Pillar",
            "OWASP Secure-by-Design Principles",
            "OWASP ASVS (Application Security Verification Standard)",
            "NIST CSF 2.0",
            "ISO/IEC 27001:2022 Annex A",
        ],
        checks=[
            Check("3.A", "Authentication",
                  "How are users and systems authenticated? Is MFA addressed for human access? "
                  "Are service-to-service auth mechanisms described?"),
            Check("3.B", "Authorisation and least privilege",
                  "How are permissions structured? Are role boundaries described? Is least "
                  "privilege applied?"),
            Check("3.C", "Defence in depth",
                  "Are security controls layered, or does the design rely on a single control?"),
            Check("3.D", "Data protection — in transit and at rest",
                  "Is encryption-in-transit specified for sensitive data flows? Is "
                  "encryption-at-rest specified for sensitive stored data?"),
            Check("3.E", "Secrets management",
                  "How are secrets (API keys, passwords, certificates) stored, rotated, accessed?"),
            Check("3.F", "Attack surface reduction",
                  "Are network boundaries described? Are public-facing components minimised?"),
            Check("3.G", "Audit logging",
                  "Are security-relevant events logged? Where? With what retention? Tamper-evident?"),
        ],
        severity_rules={
            "High": "Sensitive data handled without encryption; no authentication described; secrets in plain text.",
            "Medium": "Controls described but defence in depth absent; audit logging partial.",
            "Low": "Specific control needs clarification; values implied but not documented.",
        },
        boundaries=[
            "Does not perform security testing or vulnerability analysis.",
            "Does not validate specific cryptographic algorithms.",
        ],
    ),

    # ====================================================================
    Standard(
        id=4,
        name="Scalability & Performance Design",
        purpose=(
            "Check whether the design has named its performance and scalability constraints, "
            "and whether the design's structure is consistent with meeting them."
        ),
        authorities=[
            "AWS Well-Architected Performance Efficiency Pillar",
            "Azure Well-Architected Performance Efficiency Pillar",
            "ISO/IEC 25010:2023 — Quality model",
            "Site Reliability Engineering (Google) — high-scale architecture practice",
        ],
        checks=[
            Check("4.A", "Horizontal scalability",
                  "Can the design scale by adding capacity? Are stateful components blocking "
                  "horizontal scaling?"),
            Check("4.B", "State management",
                  "Where is state held? Is session state local or distributed? Are there "
                  "sticky-session dependencies?"),
            Check("4.C", "Caching strategy",
                  "Is caching used where appropriate? Are cache invalidation rules described?"),
            Check("4.D", "Bottleneck identification",
                  "Has the architect named the components most likely to bottleneck?"),
            Check("4.E", "Data access patterns",
                  "Are data access patterns described? Are query shapes considered (read-heavy "
                  "vs write-heavy)?"),
            Check("4.F", "Performance targets",
                  "Are quantitative performance targets stated (throughput, latency, concurrent "
                  "users)? Consistent with chosen design?"),
        ],
        severity_rules={
            "High": "Stated targets cannot be met by described design (e.g., 10K concurrent users behind a single non-scalable component).",
            "Medium": "Performance targets stated but bottleneck not identified; caching used without invalidation rules.",
            "Low": "Performance targets not stated; scaling characteristics implied but not documented.",
        },
        boundaries=[
            "Does not benchmark or test actual performance.",
            "Does not require performance targets to be met — flags inconsistency.",
        ],
    ),

    # ====================================================================
    Standard(
        id=5,
        name="Integration Pattern Validity",
        purpose=(
            "Check that integrations follow established patterns — appropriate synchronisation "
            "choice, idempotency, error handling, contract definition, and back-pressure. The "
            "majority of production incidents originate at integration boundaries."
        ),
        authorities=[
            "Enterprise Integration Patterns (Hohpe & Woolf)",
            "AWS Well-Architected REL05 & REL06",
            "TOGAF Software Services & Middleware Checklist",
            "Microservices Patterns (Chris Richardson)",
        ],
        checks=[
            Check("5.A", "Synchronous vs asynchronous appropriateness",
                  "Is synchronisation choice appropriate for the use case? Synchronous chains "
                  "where async would be more resilient; async where synchronous response is required."),
            Check("5.B", "Idempotency",
                  "For retryable operations, is idempotency addressed? Critical for financial "
                  "and notification operations."),
            Check("5.C", "Error handling at the boundary",
                  "For each integration: timeout, retry, dead-letter, circuit breaker, fallback "
                  "— what is specified?"),
            Check("5.D", "Contract and schema",
                  "Is the integration contract defined? Versioning strategy? How are breaking "
                  "changes coordinated with consumers?"),
            Check("5.E", "Coupling and anti-patterns",
                  "Point-to-point proliferation; shared databases as integration mechanism; "
                  "chatty integrations requiring many round-trips."),
            Check("5.F", "Volume and back-pressure",
                  "Are throughput limits considered? Is back-pressure or throttling described?"),
        ],
        severity_rules={
            "High": "Integration pattern materially wrong for the use case; financial operation without idempotency; sync chain across external systems with no resilience.",
            "Medium": "Significant gap; integration would work but is fragile (no DLQ on async; no contract versioning).",
            "Low": "Timeout or retry implied but not stated.",
        },
        boundaries=[
            "Does not assess broker/platform choice.",
            "Does not validate specific protocol choice (REST vs GraphQL vs gRPC).",
        ],
    ),

    # ====================================================================
    Standard(
        id=6,
        name="Data Architecture Soundness",
        purpose=(
            "Check foundational data concerns — master data ownership, lineage, classification, "
            "retention, consistency, and quality. Data mistakes are the most expensive to fix "
            "because they accumulate."
        ),
        authorities=[
            "TOGAF Phase C — Data Architecture",
            "DAMA-DMBOK (Data Management Body of Knowledge)",
            "GDPR Article 30 — Records of Processing Activities",
            "BCBS 239 (Risk Data Aggregation)",
            "ISO 8000 (Data Quality)",
        ],
        checks=[
            Check("6.A", "Master data ownership",
                  "For every shared data entity, is the system of record identified? Are "
                  "propagation directions stated?"),
            Check("6.B", "Data lineage",
                  "For each entity, is it clear where it originates and how it propagates? Are "
                  "transformations documented?"),
            Check("6.C", "Data classification and sensitivity",
                  "Are sensitive entities (PII, payment data, health data) tagged? Is the "
                  "classification standard referenced?"),
            Check("6.D", "Retention, archival, and deletion",
                  "Is the lifecycle of stored data documented? Does it satisfy GDPR "
                  "right-to-deletion?"),
            Check("6.E", "Consistency and synchronisation",
                  "Where data is duplicated, is the synchronisation strategy explicit? Is "
                  "conflict resolution described?"),
            Check("6.F", "Data quality and validation",
                  "Are validation rules described at ingestion points? Is reconciliation "
                  "between source and target addressed?"),
        ],
        severity_rules={
            "High": "Same entity mastered in multiple systems with no sync; PII stored without retention policy; no validation on ingestion.",
            "Medium": "Lineage partial; classification implicit; sync mentioned but not detailed.",
            "Low": "Clarification opportunity; ownership inferable but not stated.",
        },
        boundaries=[
            "Does not validate the logical data model (relationships, normalisation).",
            "Does not assess specific retention period values.",
        ],
    ),

    # ====================================================================
    Standard(
        id=7,
        name="Operability & Observability Design",
        purpose=(
            "Check that the design names the operational primitives — logging, metrics, "
            "alerting, tracing, deployment, rollback, and support model — required to run the "
            "system in production. A system that works on day one but cannot be operated on "
            "day 100 is a failed delivery."
        ),
        authorities=[
            "AWS Well-Architected Operational Excellence Pillar",
            "Google SRE Book — four golden signals (latency, traffic, errors, saturation)",
            "OpenTelemetry (CNCF) — logs, metrics, traces",
            "ITIL v4 Service Operation",
            "TOGAF System Management Checklist",
        ],
        checks=[
            Check("7.A", "Logging strategy",
                  "What is logged, at what level, in what format, to what destination, with "
                  "what retention?"),
            Check("7.B", "Metrics and monitoring",
                  "Are technical metrics defined (the four golden signals)? Are business "
                  "metrics defined? Is the monitoring tool named?"),
            Check("7.C", "Alerting and incident response",
                  "Are alert conditions defined? Is alert ownership clear? Is the incident "
                  "response process documented?"),
            Check("7.D", "Distributed tracing",
                  "For multi-component systems, is trace propagation described? Are "
                  "correlation IDs in interface contracts?"),
            Check("7.E", "Deployment strategy",
                  "How does the system get to production? CI/CD? Rolling, blue-green, canary?"),
            Check("7.F", "Rollback and change safety",
                  "Is the rollback procedure described? Are risky changes protected by feature "
                  "flags or staged rollout?"),
            Check("7.G", "Support model and runbooks",
                  "Who runs this in production? On-call model? Escalation? Runbooks for "
                  "common procedures?"),
        ],
        severity_rules={
            "High": "No observability strategy in document; no deployment strategy; no support model defined.",
            "Medium": "Significant gap in one dimension (logging without metrics; deployment without rollback).",
            "Low": "Partial coverage; specific values needed for clarity.",
        },
        boundaries=[
            "Does not validate specific alerting thresholds.",
            "Does not assess tooling quality.",
        ],
    ),

    # ====================================================================
    Standard(
        id=8,
        name="Technology Choice Justification",
        purpose=(
            "Check that significant technology choices are explicitly identified as decisions, "
            "that alternatives were considered, that rationale is substantive, that trade-offs "
            "are acknowledged, and that reversibility is addressed for hard-to-reverse choices."
        ),
        authorities=[
            "Architecture Decision Records (Michael Nygard, Martin Fowler)",
            "Microsoft Azure Well-Architected — ADR practice",
            "AWS Architecture Blog — ADR best practices",
            "arc42 Section 9 — Architectural Decisions",
            "TOGAF Phase G — decision capture in Architecture Repository",
        ],
        checks=[
            Check("8.A", "Decision identification",
                  "Are significant technology choices explicitly identified as decisions, or "
                  "buried in narrative?"),
            Check("8.B", "Alternatives considered",
                  "For each decision, are at least two serious alternatives listed and compared?"),
            Check("8.C", "Rationale quality",
                  "Is the rationale substantive — citing specific factors — or circular?"),
            Check("8.D", "Trade-offs and consequences",
                  "Are downsides and trade-offs explicitly acknowledged?"),
            Check("8.E", "Status and reversibility",
                  "For hard-to-reverse decisions (data model, vendor commitment, language), "
                  "is reversibility cost addressed?"),
        ],
        severity_rules={
            "High": "Significant technology choices with no rationale, or circular rationale, especially for hard-to-reverse decisions.",
            "Medium": "Rationale present but missing alternatives, missing trade-offs, or external-only references.",
            "Low": "Minor decisions or clarification opportunities.",
        },
        boundaries=[
            "Does not assess whether the chosen technology is actually right.",
            "Does not validate cost or performance claims in rationales.",
        ],
    ),

    # ====================================================================
    Standard(
        id=9,
        name="Compliance & Regulatory Surface",
        purpose=(
            "Surface which regulations apply based on the data and operations involved, and "
            "whether the design addresses the architectural requirements of those regulations. "
            "Not a legal opinion — a surface-and-check function."
        ),
        authorities=[
            "GDPR (EU and UK) — Articles 5, 25, 30, 32, 35",
            "PCI-DSS v4.0",
            "HIPAA Security Rule (45 CFR Part 164)",
            "SOX Sections 302 and 404",
            "ISO/IEC 27001:2022",
            "DORA (Digital Operational Resilience Act)",
        ],
        checks=[
            Check("9.A", "Regulatory surface identification",
                  "Has the HLD identified which regulations apply based on the data and "
                  "operations involved?"),
            Check("9.B", "Data residency and cross-border flows",
                  "Where cross-border flows occur, are residency requirements and transfer "
                  "mechanisms (SCCs, adequacy decisions) addressed?"),
            Check("9.C", "Audit trail for regulated operations",
                  "Are regulated operations audit-logged with appropriate retention? PCI-DSS "
                  "requires 12 months; SOX requires 7 years."),
            Check("9.D", "Consent, deletion, and subject rights",
                  "For personal data: lawful basis stated? Mechanisms for DSAR, deletion, "
                  "portability?"),
            Check("9.E", "Encryption and key management",
                  "Is sensitive data encrypted at rest and in transit? Is key management "
                  "described?"),
            Check("9.F", "Vendor and third-party risk",
                  "Where third parties process regulated data, are DPAs and processor "
                  "certifications addressed?"),
        ],
        severity_rules={
            "High": "Material regulatory framework applies but is not addressed at all.",
            "Medium": "Framework mentioned but specific architectural controls missing.",
            "Low": "Framework partially addressed; clarification needed.",
        },
        boundaries=[
            "Does not provide a legal opinion on whether a regulation applies.",
            "Does not validate that specific controls are correctly implemented.",
        ],
    ),

    # ====================================================================
    Standard(
        id=10,
        name="Architectural Coherence & Trade-off Transparency",
        purpose=(
            "Check that the design acknowledges its compromises — quality attribute conflicts, "
            "distributed-systems trade-offs, cost-capability balance, flexibility-complexity "
            "tension. A design that acknowledges its trade-offs is designing intentionally."
        ),
        authorities=[
            "ISO/IEC 25010:2023 — quality attribute model",
            "CAP Theorem (Brewer 2000; Gilbert & Lynch 2002)",
            "PACELC (Daniel Abadi)",
            "arc42 Section 10 — Quality Requirements",
            "AWS Well-Architected — trade-off principles",
        ],
        checks=[
            Check("10.A", "Quality attribute conflicts",
                  "Are multiple quality attributes claimed at maximum levels simultaneously "
                  "without acknowledging conflict?"),
            Check("10.B", "Distributed-systems trade-offs",
                  "For multi-region or multi-database designs: is the consistency model "
                  "stated? CAP / PACELC implications addressed?"),
            Check("10.C", "Cost / capability trade-off",
                  "Are premium-tier or multi-region active-active choices accompanied by cost "
                  "discussion?"),
            Check("10.D", "Flexibility / complexity trade-off",
                  "Are 'highly flexible' or 'future-proof' claims accompanied by "
                  "acknowledgement of complexity cost?"),
            Check("10.E", "Implicit vs explicit trade-offs",
                  "Is there an explicit Trade-offs section, or are choices presented as "
                  "universally optimal?"),
        ],
        severity_rules={
            "High": "Design makes physically impossible claims (CAP violations) or major contradictions.",
            "Medium": "Design ignores major trade-offs (no consistency model on distributed system; no cost discussion on premium choices).",
            "Low": "Implicit trade-offs that should be made explicit.",
        },
        boundaries=[
            "Does not judge whether the chosen trade-offs are correct.",
            "Does not enforce a specific quality attribute prioritisation.",
        ],
    ),
]


def get_standard(standard_id: int) -> Standard:
    """Look up a standard by its ID (1-10)."""
    for std in STANDARDS:
        if std.id == standard_id:
            return std
    raise ValueError(f"Standard {standard_id} not found")
