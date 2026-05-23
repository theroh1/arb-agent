"""
ARB Pre-Review Agent — Streamlit app.

Run locally:
    streamlit run app.py

Deploy to Streamlit Cloud:
    Push the folder to GitHub, point Streamlit Cloud at app.py, set
    ANTHROPIC_API_KEY in the app's Secrets.
"""
import os
import time
from io import BytesIO

import streamlit as st

# Load .env if present (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from arb_agent.extractor import extract_from_bytes
from arb_agent.checker import run_review, DEFAULT_MODEL
from arb_agent.reporter import build_markdown_report, build_docx_report
from arb_agent.standards import STANDARDS


# =============================================================================
# Page config
# =============================================================================
st.set_page_config(
    page_title="ARB Pre-Review Agent",
    page_icon="🟣",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =============================================================================
# Accenture-themed CSS
# =============================================================================
ACCENTURE_CSS = """
<style>
  :root {
    --purple: #A100FF;
    --purple-deep: #7A00C2;
    --purple-soft: #CD7DFF;
    --purple-tint: #F4E5FF;
    --purple-wash: #FAF1FF;
    --text: #1A1A1A;
    --text-muted: #525252;
    --text-faint: #8E8E8E;
    --high: #BE123C;
    --medium: #B45309;
    --low: #0F766E;
  }

  /* Title styling */
  .eyebrow {
    color: var(--purple);
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 4px;
  }
  .hero-title {
    font-size: 36px;
    font-weight: 800;
    color: #000;
    margin: 0 0 6px 0;
    line-height: 1.15;
  }
  .hero-sub {
    color: var(--text-muted);
    font-size: 15px;
    margin: 0 0 24px 0;
    line-height: 1.5;
  }

  /* Severity pills */
  .pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1px;
  }
  .pill-high   { background: #FEE2E2; color: var(--high); }
  .pill-medium { background: #FEF3C7; color: var(--medium); }
  .pill-low    { background: #D1FAE5; color: var(--low); }

  /* Finding card */
  .finding {
    border: 1px solid #E5E5E5;
    border-left: 4px solid var(--purple);
    border-radius: 4px;
    padding: 14px 18px;
    margin: 12px 0;
    background: #FFFFFF;
  }
  .finding.high   { border-left-color: var(--high); }
  .finding.medium { border-left-color: var(--medium); }
  .finding.low    { border-left-color: var(--low); }

  .finding h4 {
    margin: 0 0 8px 0;
    color: #000;
    font-size: 15px;
  }
  .finding .field-label {
    color: var(--purple-deep);
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 8px;
  }
  .finding .field-value {
    color: var(--text);
    font-size: 14px;
    line-height: 1.5;
    margin-top: 2px;
  }
  .finding .quote {
    background: var(--purple-wash);
    border-left: 3px solid var(--purple-soft);
    padding: 6px 10px;
    font-style: italic;
    color: var(--text-muted);
    margin: 4px 0;
    font-size: 13px;
  }

  /* Big severity counters */
  .counter-row { display: flex; gap: 12px; margin: 8px 0 20px 0; }
  .counter {
    flex: 1;
    border: 1px solid #E5E5E5;
    border-radius: 4px;
    padding: 14px 18px;
    background: #FAFAFA;
  }
  .counter .label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    color: var(--text-muted);
  }
  .counter .value {
    font-size: 36px;
    font-weight: 800;
    margin-top: 4px;
  }
  .counter.high   .label { color: var(--high); }
  .counter.medium .label { color: var(--medium); }
  .counter.low    .label { color: var(--low); }
  .counter.total  .label { color: var(--purple); }
  .counter.high   .value { color: var(--high); }
  .counter.medium .value { color: var(--medium); }
  .counter.low    .value { color: var(--low); }
  .counter.total  .value { color: #000; }

  /* Status table */
  .status-clear { color: var(--low); font-weight: 600; }
  .status-warn  { color: var(--high); font-weight: 700; }
  .status-some  { color: var(--medium); font-weight: 600; }
  .status-err   { color: var(--high); font-weight: 700; }
</style>
"""
st.markdown(ACCENTURE_CSS, unsafe_allow_html=True)


# =============================================================================
# Header
# =============================================================================
st.markdown('<div class="eyebrow">Architecture Governance · AI Pre-Review</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">ARB Pre-Review Agent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Upload a High-Level Design. The agent evaluates it against ten universal architectural standards and returns a structured pre-review report. The agent flags, the board decides.</div>',
    unsafe_allow_html=True,
)


# =============================================================================
# Helpers — get Bedrock configuration
# =============================================================================
def _secret_or_env(name: str, default: str | None = None) -> str | None:
    """Streamlit Cloud secrets take priority, then env vars."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


def get_bedrock_token() -> str | None:
    """Bedrock API key (short-term bearer token)."""
    return _secret_or_env("AWS_BEARER_TOKEN_BEDROCK")


def get_region() -> str:
    return (
        _secret_or_env("AWS_REGION")
        or _secret_or_env("AWS_DEFAULT_REGION")
        or "us-east-1"
    )


def get_model() -> str:
    return _secret_or_env("BEDROCK_MODEL_ID", DEFAULT_MODEL)


# =============================================================================
# Upload section
# =============================================================================
col_upload, col_meta = st.columns([2, 1])

with col_upload:
    uploaded = st.file_uploader(
        "Upload your HLD (.docx or .pdf)",
        type=["docx", "pdf"],
        accept_multiple_files=False,
        help="The agent extracts the document content and evaluates it against ten universal architectural standards.",
    )

with col_meta:
    st.markdown("**The ten standards**")
    for std in STANDARDS:
        st.markdown(
            f"<div style='font-size:13px;color:#525252;line-height:1.5;'><span style='color:#A100FF;font-weight:700;'>{std.display_id}</span> &nbsp; {std.name}</div>",
            unsafe_allow_html=True,
        )

# Config sanity check
bedrock_token = get_bedrock_token()
region = get_region()
model = get_model()

# Propagate the Bedrock API key into boto3's expected env var.
# boto3 reads AWS_BEARER_TOKEN_BEDROCK directly for Bedrock service auth.
if bedrock_token:
    os.environ["AWS_BEARER_TOKEN_BEDROCK"] = bedrock_token

# Allow falling back to standard AWS credentials (IAM role / aws configure)
# by treating either a Bedrock token OR an AWS access key as sufficient.
has_aws_creds = bool(bedrock_token) or bool(os.environ.get("AWS_ACCESS_KEY_ID"))

if not has_aws_creds:
    st.error(
        "**AWS Bedrock credentials are not configured.** "
        "Set `AWS_BEARER_TOKEN_BEDROCK` (Bedrock API key) — or standard AWS "
        "credentials via `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — "
        "in your `.env` or Streamlit Cloud secrets, then refresh."
    )
    st.stop()


# =============================================================================
# Run review
# =============================================================================
if uploaded is not None:
    file_bytes = uploaded.read()
    file_name = uploaded.name

    st.markdown("---")

    # Extract
    with st.spinner(f"Reading {file_name}..."):
        try:
            hld = extract_from_bytes(file_name, file_bytes)
        except Exception as e:
            st.error(f"Could not read the file: {e}")
            st.stop()

    # Show extraction stats
    meta_cols = st.columns(4)
    meta_cols[0].metric("Words", f"{hld.word_count:,}")
    meta_cols[1].metric("Sections", hld.section_count)
    meta_cols[2].metric("Tables", hld.table_count)
    meta_cols[3].metric("Pages", hld.page_count or "—")

    # Start button
    if st.button("Run pre-review", type="primary", use_container_width=False):
        st.session_state["review_started"] = True
        st.session_state["hld"] = hld

    if st.session_state.get("review_started"):
        hld = st.session_state["hld"]

        # Progress UI
        st.markdown(f"_Running against `{model}` — evaluating against ten standards in sequence._")
        progress_bar = st.progress(0.0, text="Starting...")
        status_placeholder = st.empty()
        status_lines = []

        def on_progress(idx, standard, status):
            if status == "start":
                status_lines.append(f"⏳ **{standard.display_id} — {standard.name}**")
            else:
                # Remove the "in progress" version
                status_lines[-1] = (
                    f"✅ **{standard.display_id} — {standard.name}**"
                    if status == "done"
                    else f"⚠ **{standard.display_id} — {standard.name}** (error)"
                )
                progress_bar.progress(
                    (idx + 1) / len(STANDARDS),
                    text=f"Done {idx + 1}/{len(STANDARDS)} standards",
                )
            status_placeholder.markdown(
                "\n\n".join(status_lines)
            )

        # Run the review
        start = time.time()
        review = run_review(
            hld_text=hld.text,
            hld_filename=hld.filename,
            region=region,
            model=model,
            progress=on_progress,
        )
        elapsed = time.time() - start

        status_placeholder.empty()
        progress_bar.empty()

        # =====================================================================
        # Display report
        # =====================================================================
        st.markdown(f"### Pre-Review Report — `{hld.filename}`")
        st.caption(f"Completed in {elapsed:.1f}s · Model: `{review.model}`")

        # Counters
        high = review.findings_by_severity("High")
        medium = review.findings_by_severity("Medium")
        low = review.findings_by_severity("Low")
        total = review.total_findings

        st.markdown(
            f"""
        <div class="counter-row">
          <div class="counter total">
            <div class="label">TOTAL FINDINGS</div>
            <div class="value">{total}</div>
          </div>
          <div class="counter high">
            <div class="label">HIGH</div>
            <div class="value">{high}</div>
          </div>
          <div class="counter medium">
            <div class="label">MEDIUM</div>
            <div class="value">{medium}</div>
          </div>
          <div class="counter low">
            <div class="label">LOW</div>
            <div class="value">{low}</div>
          </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Download buttons
        docx_bytes = build_docx_report(review)
        md_text = build_markdown_report(review)
        d1, d2, _ = st.columns([1, 1, 4])
        with d1:
            st.download_button(
                "⬇ Download Word report",
                data=docx_bytes,
                file_name=f"Pre-Review_{hld.filename.rsplit('.', 1)[0]}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        with d2:
            st.download_button(
                "⬇ Download Markdown",
                data=md_text.encode("utf-8"),
                file_name=f"Pre-Review_{hld.filename.rsplit('.', 1)[0]}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        st.markdown("")

        # Per-standard summary table
        st.markdown("#### Status per standard")
        rows = []
        for r in review.results:
            if r.error:
                status = "⚠ Error"
            elif sum(1 for f in r.findings if f.severity == "High"):
                status = f"⚠ {sum(1 for f in r.findings if f.severity == 'High')} high"
            elif r.findings:
                status = f"{len(r.findings)} findings"
            else:
                status = "✓ Clear"
            rows.append(
                {
                    "#": r.standard.display_id,
                    "Standard": r.standard.name,
                    "Findings": len(r.findings),
                    "Status": status,
                }
            )
        st.dataframe(rows, hide_index=True, use_container_width=True)

        # Per-standard findings
        st.markdown("#### Findings by standard")
        st.markdown(
            "<div style='color:#525252;font-size:13px;margin-bottom:8px;'>Click each standard to expand its findings.</div>",
            unsafe_allow_html=True,
        )

        for r in review.results:
            label = f"{r.standard.display_id} — {r.standard.name}"
            if r.error:
                label += " · ⚠ Error"
            elif r.findings:
                label += f" · {len(r.findings)} finding{'s' if len(r.findings) != 1 else ''}"
            else:
                label += " · ✓ Clear"

            # Expand items with high-severity findings by default
            has_high = any(f.severity == "High" for f in r.findings)
            with st.expander(label, expanded=has_high):
                st.markdown(
                    f"<div style='color:#525252;font-style:italic;font-size:13px;margin-bottom:8px;'>{r.standard.purpose}</div>",
                    unsafe_allow_html=True,
                )
                if r.error:
                    st.error(f"Could not evaluate this standard: {r.error}")
                    continue
                if not r.findings:
                    st.success(
                        "No findings. Standard is satisfied or not applicable to this design."
                    )
                    continue
                for idx, f in enumerate(r.findings, start=1):
                    _render_finding(r.standard.display_id, idx, f)


def _render_finding(std_display_id: str, idx: int, f):
    """Render a single finding card."""
    finding_id = f"F-{std_display_id}.{idx}"
    sev_class = f.severity.lower()
    pill_class = f"pill-{sev_class}"

    html = f"""
    <div class="finding {sev_class}">
      <h4>
        <span style="color:#525252;font-weight:600;">{finding_id}</span>
        &nbsp;&nbsp;
        <span class="pill {pill_class}">{f.severity.upper()}</span>
        &nbsp;&nbsp;
        {f.check_id} &nbsp; {f.check_name}
      </h4>

      <div class="field-label">Issue</div>
      <div class="field-value">{_escape(f.issue)}</div>

      <div class="field-label">Evidence — {_escape(f.evidence_section)}</div>
      <div class="quote">{_escape(f.evidence_quote)}</div>

      <div class="field-label">Authority</div>
      <div class="field-value">{_escape(f.authority)}</div>

      <div class="field-label">Recommendation</div>
      <div class="field-value">{_escape(f.recommendation)}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def _escape(text: str) -> str:
    """Minimal HTML escape for user-rendered values."""
    return (
        (text or "—")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# =============================================================================
# Footer
# =============================================================================
st.markdown(
    """
<div style="margin-top:60px;padding-top:20px;border-top:1px solid #ECECEC;color:#8E8E8E;font-size:12px;">
  The agent surfaces concerns against universal architectural standards for the
  Architecture Advisory Group to evaluate. It does not approve or reject designs.
  All findings are advisory — the board retains full authority.
</div>
""",
    unsafe_allow_html=True,
)
