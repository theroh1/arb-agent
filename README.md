# ARB Pre-Review Agent

> An AI agent that reads a High-Level Design and produces a structured pre-review
> report against ten universal architectural standards — so the Architecture
> Advisory Group's meeting time can focus on judgment, not hygiene.

The agent flags. The board decides.

---

## What it does

1. **Upload** a High-Level Design (`.docx` or `.pdf`)
2. **Agent evaluates** it against ten universal standards — 59 specific checks grounded in TOGAF, AWS Well-Architected, OWASP, ISO/IEC 25010, DAMA-DMBOK, Enterprise Integration Patterns, and ADR practice
3. **Report appears** on screen with findings grouped by standard, severity, evidence (HLD section + direct quote), and recommendation
4. **Download** the report as Word or Markdown

Every finding cites both a specific location in the HLD and the published authority that defines the concern. The agent never approves or rejects — only surfaces.

---

## Quick start (local)

```bash
# 1. Install Python 3.10+ and clone/copy this folder

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure AWS Bedrock credentials
cp .env.example .env
# Edit .env and paste your Bedrock API key (AWS console → Bedrock → API keys)

# 4. Run the app
streamlit run app.py
```

The app opens in your browser. Upload an HLD and click **Run pre-review**.

---

## Share with others (Streamlit Community Cloud)

The easiest way to share this agent is via Streamlit's free hosting. Anyone you
give the URL to can use it without installing anything.

**Step 1 — Put the code on GitHub**

Create a new GitHub repository (public or private — both work). Push this
folder to it.

**Step 2 — Deploy to Streamlit Cloud**

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app**
3. Select your repository, branch (`main`), and main file path (`app.py`)
4. Click **Advanced settings** and add your Bedrock credentials to **Secrets** in this exact format:

   ```toml
   AWS_BEARER_TOKEN_BEDROCK = "ABSKBedrockAPIKey-..."
   AWS_REGION = "us-east-1"
   BEDROCK_MODEL_ID = "qwen.qwen3-coder-480b-a35b-v1:0"
   ```

5. Click **Deploy**

The app gets a public URL in 1–2 minutes. Share it with anyone.

**Notes on access control.** Streamlit Community Cloud lets you make the app
private (visible only to specific Google accounts you authorise) under the
app's settings. Use that if your HLDs are sensitive.

---

## Other deployment options

- **Run locally and share over LAN.** Run `streamlit run app.py --server.address=0.0.0.0`. Others on the same network reach it at `http://YOUR_IP:8501`.
- **Docker.** Containerise with a slim Python image, expose port 8501, set `AWS_BEARER_TOKEN_BEDROCK` and `AWS_REGION` as env vars. Deploy to any cloud (Fly.io, Railway, ECS, Cloud Run).
- **Self-hosted server.** Standard Streamlit deployment on any server you control. On EC2 or ECS, prefer an IAM role with `bedrock:InvokeModel` permission over a long-lived API key.

---

## Project layout

```
arb_agent/
├── app.py                  Streamlit UI
├── arb_agent/              The agent module
│   ├── standards.py        The 10 standards & 59 checks (the rubric)
│   ├── extractor.py        Reads .docx and .pdf HLDs
│   ├── prompts.py          Constructs grounded prompts per standard
│   ├── checker.py          Orchestrates LLM calls and parses findings
│   ├── reporter.py         Builds Word & Markdown reports
│   └── models.py           Pure data classes (no SDK deps)
├── requirements.txt
├── .env.example
└── README.md
```

---

## How it works under the hood

For each of the ten standards, the agent:

1. **Builds a structured prompt** that includes the standard's purpose, the authorities that ground it, the specific checks to perform, the severity calibration rules, and the full HLD content
2. **Calls AWS Bedrock** (Qwen model via the Converse API) with a strict instruction to output JSON only — every finding must cite an HLD section, a direct quote, and an authority
3. **Parses the JSON** and constructs `Finding` objects with validated severity
4. **Sorts** by severity (High → Medium → Low) within each standard

The system prompt encodes three absolute rules:

- **Evidence or nothing** — no findings without HLD location + quote
- **Authority citation** — every finding names the source that defines it
- **Strict JSON** — machine-parseable output, no commentary

If the LLM violates these or returns malformed JSON, the agent retries once
with stricter framing. If that also fails, it records an error for that
standard and continues with the others.

---

## Configuration

Environment variables (set in `.env`, OS env, or Streamlit Cloud secrets):

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `AWS_BEARER_TOKEN_BEDROCK` | yes* | — | Bedrock API key from AWS Console → Bedrock → API keys |
| `AWS_REGION` | yes | `us-east-1` | Must be a region where your Qwen model is enabled |
| `BEDROCK_MODEL_ID` | no | `qwen.qwen3-coder-480b-a35b-v1:0` | Any Qwen model ID available in your account |

\* Alternatively, supply standard AWS credentials (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`) or attach an IAM role with `bedrock:InvokeModel` permission to the host.

**Model recommendations.** For HLD review (reasoning + structured JSON output), `qwen.qwen3-235b-a22b-2507-v1:0` (general) typically outperforms the coder variant despite being smaller. Override `BEDROCK_MODEL_ID` to test.

---

## Cost per review

Approximate, for a 25,000-word HLD:

- Input: ~150K tokens × 10 calls = 1.5M input tokens
- Output: ~1K tokens × 10 calls = 10K output tokens

Actual cost depends on the Qwen variant and current Bedrock pricing. Verify in the [AWS Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) — Qwen models on Bedrock Marketplace are billed per-token. The smaller Qwen3 32B is materially cheaper than the 235B or 480B variants.

---

## Adapting the agent

**The ten standards live in `arb_agent/standards.py`.** To adapt the agent to
your organisation's specific governance principles:

- Add a new `Standard` object to the `STANDARDS` list — same structure as the others
- Add or modify `Check` objects within each standard
- Update severity calibration rules per standard
- Cite the authority backing each rule

The prompt construction (`prompts.py`) and the report generator (`reporter.py`)
adapt automatically — no other code changes required.

---

## What the agent does NOT do

The agent is deliberately constrained:

- It does not approve or reject designs — only flags concerns for the AAG
- It does not assess client-specific or domain-bespoke standards — universal hygiene only
- It does not perform security testing, performance benchmarking, or any inspection beyond document review
- It does not replace any human governance tier
- It does not invent findings — if the evidence isn't in the document, the agent says so

These boundaries preserve the AAG's authority and ensure every finding is
defensible.

---

## Troubleshooting

**"AWS Bedrock credentials are not configured"** — set `AWS_BEARER_TOKEN_BEDROCK`
(or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`) in `.env` / Streamlit Cloud
secrets, then refresh the browser.

**`AccessDeniedException` or `ValidationException` from Bedrock** — the model
ID is not enabled in the configured `AWS_REGION`. In the AWS console, go to
Bedrock → Model access (or Marketplace for Qwen) and request access; or change
`AWS_REGION` to a region where the model is enabled.

**"Could not read the file"** — confirm the file is a valid `.docx` or `.pdf`.
Scanned PDFs without OCR will extract empty text.

**Slow first run** — Streamlit warms up on first use. Subsequent reviews start
faster. Each review takes 30–90 seconds depending on HLD size and model.

**JSON parse errors on a standard** — the agent retries once and records an
error. The other nine standards still produce findings. The Word report calls
out errored standards explicitly.

---

## Licence

Internal use within your organisation. Customise freely.
