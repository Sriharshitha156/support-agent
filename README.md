# Customer Support Resolution Agent

A capstone project that builds an AI-powered customer support agent using **LangGraph**, **LangChain**, **FastAPI**, and **Streamlit**. The agent handles order inquiries, refund requests, policy lookups, and human-in-the-loop escalation with full audit logging.

**Repository:** [github.com/Sriharshitha156/support-agent](https://github.com/Sriharshitha156/support-agent)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Agent orchestration | LangGraph, LangChain |
| API backend | FastAPI, Uvicorn |
| Frontend | Streamlit |
| RAG / vector store | ChromaDB (Chroma) |
| LLM | GPT-4o-mini (GitHub Models / OpenRouter / OpenAI) |
| Embeddings | Google Gemini (primary), OpenAI, GitHub Models, local HashingEmbeddings |
| Validation | Pydantic |
| Unit / integration tests | Pytest |
| E2E browser tests | Playwright |

---

## Project Structure

```
support-agent/
├── app.py                      # FastAPI backend entry point
├── ui.py                       # Streamlit "AI Operations Command Center" dashboard
├── eval_suite.py               # Evaluation suite (5 capstone scenarios)
├── PROJECT_EXPLAINED.txt       # Comprehensive project documentation
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest config (pythonpath)
├── setup.ps1 / setup.sh        # Virtual environment setup
├── .env.example                # Environment variable template
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app with /chat, /approve, /get_audit_log, /health
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py            # AgentState TypedDict schema
│   │   ├── nodes.py            # preprocess, planner, human_gate, tool_executor nodes
│   │   └── graph.py            # LangGraph StateGraph, routing, compilation
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── support_tools.py    # check_order_status, apply_refund, send_goodwill_credit
│   │   ├── order_lookup.py     # Structured order lookup with ownership validation
│   │   ├── refund_tool.py      # Structured refund processing with validation
│   │   └── human_gate.py       # Escalation ticket generation
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── policy_retriever.py # High-level policy retrieval interface
│   │   ├── vectorstore.py      # ChromaDB vector store + embedding fallback chain
│   │   └── ingestion.py        # Policy document ingestion pipeline
│   └── governance/
│       ├── __init__.py
│       ├── audit.py            # log_event() → data/audit_log.json
│       └── refusal.py          # PII scan + compliance verification
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Shared pytest fixtures
│   ├── test_agent.py           # LangGraph integration tests (8 cases)
│   ├── test_support_tools.py   # Support tool unit tests
│   ├── test_tools.py           # Mock order lookup tests
│   ├── test_rag.py             # Policy retrieval tests
│   ├── test_governance.py      # Audit logging tests
│   ├── test_api.py             # FastAPI endpoint tests
│   └── test_e2e.py             # Playwright E2E browser tests (14 cases)
└── data/
    ├── mock_orders.py          # 16 mock orders + lookup_order()
    ├── policies.txt            # Flat text policies for RAG
    ├── orders/
    │   └── mock_orders.json    # Legacy sample orders (JSON fallback)
    ├── policies/
    │   ├── refund_policy.md
    │   ├── shipping_policy.md
    │   ├── privacy_policy.md
    │   ├── warranty_policy.md
    │   ├── return_policy.md
    │   ├── account_security_policy.md
    │   ├── loyalty_policy.md
    │   ├── complaint_policy.md
    │   └── product_safety_policy.md
    └── audit_log.json          # Runtime-generated audit trail
```

---

## Quick Start

### 1. Clone and set up the environment

```powershell
git clone https://github.com/Sriharshitha156/support-agent.git
cd support-agent
.\setup.ps1
```

On macOS/Linux:

```bash
chmod +x setup.sh && ./setup.sh
```

### 2. Configure API keys

```powershell
copy .env.example .env
```

Edit `.env` and set your API keys:

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub PAT for LLM (GPT-4o-mini) + embedding fallback |
| `GOOGLE_API_KEY` | No | Google Gemini embeddings (free tier, 1500 req/day) |
| `OPENAI_API_KEY` | No | OpenRouter key for LLM/embedding fallback |
| `CHROMA_PERSIST_DIR` | No | ChromaDB storage path (default: `./data/chroma_db`) |

### 3. Run tests

```powershell
.\venv\Scripts\Activate.ps1
pytest tests/ -v
```

### 4. Run the app

**Streamlit demo (recommended for capstone demo):**

```powershell
streamlit run ui.py
```

**FastAPI backend (optional — for API clients):**

```powershell
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

---

## Implementation Progress

> This section is updated as each milestone is completed.

### Step 1 — Repository & environment setup ✅

- Initialized Git repo and connected to GitHub
- Added `.gitignore` (excludes `venv/`, `.env`, generated data)
- Added Cursor rule for auto-sync commits to GitHub
- Removed Cursor co-author trailers from commit history

### Step 2 — Project scaffold ✅

- Created production folder structure (`app/`, `tests/`, `data/`)
- Added `requirements.txt` with all core dependencies
- Added `setup.ps1` and `setup.sh` for virtual environment setup
- Added `.env.example` for API key configuration
- Added placeholder modules with docstrings in every package
- Added mock data:
  - `data/orders/mock_orders.json` — sample orders
  - `data/policies/` — refund, shipping, and privacy policies

### Step 3 — LangGraph core agent ✅

Implemented in `app/agent/graph.py` and `app/agent/state.py`:

| Component | Status | Description |
|-----------|--------|-------------|
| `AgentState` | ✅ Done | State keys: `messages`, `order_id`, `refund_amount`, `requires_human_approval`, `audit_log` |
| Planner node | ✅ Done | LLM intent detection (structured output) with robust local regex fallback |
| Human Gate node | ✅ Done | Pauses via `interrupt()` when approval is required |
| Tool Executor node | ✅ Done | Runs mock tools only when approval is granted or not needed |
| Graph compilation | ✅ Done | `MemorySaver` checkpointer for session persistence |
| Audit logging | ✅ Done | JSON log entry appended at every step |
| Tests | ✅ Done | 5 pytest scenarios in `tests/test_agent.py` — all passing |

**Agent flow:**

```
User message → Preprocess → Planner → [Human Gate | Tool Executor] → Response
Human Gate: Wait → Approve/Reject → [Tool Executor | End]
```

**Escalation rules (enforced by Preprocess + Human Gate):**

- Refund amount **> $10** → `requires_human_approval = True`; `apply_refund` blocked
- Legal keywords **sue / lawyer / legal** on refund requests → human gate required
- Risk scan keywords: `sue`, `lawyer`, `legal`, `refund`, `compensation`
- Order status queries → `check_order_status()`
- Small refunds (≤ $10) → `apply_refund()` after policy retrieval

**Usage example:**

```python
from app.agent import invoke_agent, resume_human_gate

# Normal flow
result = invoke_agent("What is my order status for C1234?", thread_id="session-1")

# High-value refund — pauses at human gate
result = invoke_agent("Refund $25 for B9999", thread_id="session-2")
if result.get("gate_response", {}).get("type") == "WAITING_APPROVAL":
    approved = resume_human_gate("approve", thread_id="session-2")
    rejected = resume_human_gate("reject", thread_id="session-2")
```

### Step 4 — Supporting modules & real integrations ✅

| Module | File | Description |
|--------|------|-------------|
| Mock orders | `data/mock_orders.py` | 5 fake orders (A4821 late, B9999 high-value, C1234 normal, +2 more); `lookup_order()` |
| Support tools | `app/tools/support_tools.py` | `check_order_status`, `apply_refund` (≤ $10 only), `send_goodwill_credit` |
| Order Lookup | `app/tools/order_lookup.py` | Structured tool querying JSON db with ownership validation |
| Refund Tool | `app/tools/refund_tool.py` | Structured tool validating refund window, limits, and eligibility |
| Human Gate Tool | `app/tools/human_gate.py` | Escalation structured tool generating tickets and logging handoff |
| Policy RAG | `app/rag/policy_retriever.py` | Query policies from ChromaDB with self-healing ingestion support |
| Vector Store | `app/rag/vectorstore.py` | Persistent ChromaDB collection wrapper (API-key check & `HashingEmbeddings` offline fallback) |
| Ingestion | `app/rag/ingestion.py` | Pipeline loading/chunking docs from `data/policies/` and `policies.txt` to ChromaDB |
| Compliance Refusal | `app/governance/refusal.py` | Audits agent response to block PII exposure and enforce refund eligibility |
| Governance | `app/governance/audit.py` | `log_event()` persists every agent step to `data/audit_log.json` |
| Agent graph | `app/agent/graph.py` | Updated to call real tools, policy retriever, and compliance refusal checks |

### Step 5 — Strict Human Gate enforcement ✅

| Feature | Description |
|---------|-------------|
| Preprocess node | Scans `sue`, `lawyer`, `legal`, `refund`, `compensation` before planning |
| `WAITING_APPROVAL` | Returns `{"type": "WAITING_APPROVAL", "reason": "High value refund or legal threat detected."}` |
| `RISK_DETECTED` | Governance log entry: `"RISK_DETECTED: Escalating to human."` |
| `approve_human_action()` | `"approve"` clears flag and routes to tool executor; `"reject"` ends with polite refusal |
| Refund safety | `apply_refund` never called when `requires_human_approval` is `True` |

### Step 6 — FastAPI backend ✅

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Send message + `session_id`, get agent response |
| `/approve` | POST | Send `session_id` + `decision` (`approve`/`reject`) |
| `/get_audit_log` | GET | Last 10 governance audit events |
| `/health` | GET | Liveness check |

Run: `uvicorn app.main:app --reload`

### Step 7 — Streamlit UI (AI Operations Command Center) ✅

Futuristic AI Mission Control Dashboard (`streamlit run ui.py`):

- **Premium HUD Aesthetics**: Deep slate/black backdrop theme with glassmorphic cards (`backdrop-filter blur`), gradient highlights, and a modern layout inspired by OpenAI Operator and Palantir Foundry.
- **Real-Time Live Workflow Path & Badges**: SVG path nodes light up and animate in real time as the pipeline runs, showing active supervisor agent badges (`IDLE`, `ACTIVE`, `WAITING`, `ESCALATED`) changing dynamically in the left sidebar as tasks are routed.
- **Supervisor Agent Net Panel**: Displays the live statuses and task/reasoning parameters of all supervisor nodes in the sidebar (Support, Compliance, Risk, Research, and Finance Agents) in expanding drawers.
- **Live Tool Calls Stream & Diagnostics HUD**: Monospace terminal panel showing real-time timestamps, actions, status results, and execution duration for DB lookups, vector searches, and system updates.
- **Fail-Safe Override Controls**: A pulse-red manager override warning panel displaying recommended actions and inline controls (APPROVE / REJECT) alongside Streamlit's native `@st.dialog` modal.
- **Interactive Structured Diagnostics Tabs**: Overhauled bottom console tabs—particularly the **📜 Audit Log** and **🧠 Reasoning Trace**—replacing raw JSON logs with beautifully structured expansion cards, risk category filters, and step-by-step reasoning layouts.
- **Live Metrics HUD**: Tracks Resolutions Automated, Average Response Latency, Citation Accuracy, Pending Escalations, and Saved Operating Cost in a top operations header.

### Step 8 — Evaluation suite ✅

Five capstone scenarios in `eval_suite.py`:

| # | Test | Expected behavior |
|---|------|-------------------|
| 1 | Happy Path | Order A4821 status + policy citation, no escalation |
| 2 | Small Refund ($5) | Auto-approve late-order refund, cite policy |
| 3 | Large Refund ($300) | Human gate, RISK_DETECTED, no refund |
| 4 | Out of Scope | Refuse competitor comparison |
| 5 | Adversarial | Ignore jailbreak, trigger human gate for $500 |

```powershell
python eval_suite.py          # writes evaluation_report.json
pytest eval_suite.py -v       # run as pytest
```

Report fields per test: **Pass/Fail**, **latency_ms**, **token_usage** (mocked), **audit_log_snippet**.

**Mock order scenarios (16 orders):**

| Order ID | Customer | Status | Total | Scenario |
|----------|----------|--------|-------|----------|
| A4821 | cust_1001 | shipped | $89.99 | Late delivery (5 days) |
| B9999 | cust_1002 | delivered | $500.00 | High value, approval required |
| C1234 | cust_1003 | shipped | $34.50 | Normal shipped status |
| D5678 | cust_1004 | processing | $120.00 | Still processing |
| E9012 | cust_1005 | cancelled | $45.00 | Cancelled order |
| F2345 | cust_1006 | delivered | $15.99 | Small delivered order |
| G6789 | cust_1007 | delivered | $749.00 | Premium electronics |
| H0123 | cust_1008 | shipped | $22.50 | Gift order |
| I4567 | cust_1009 | processing | $999.99 | Very high value |
| J8901 | cust_1010 | delivered | $8.50 | Small value (auto-refund eligible) |
| K2345 | cust_1011 | shipped | $156.75 | International order |
| L6789 | cust_1012 | delivered | $320.00 | Return requested |
| M0123 | cust_1013 | cancelled | $67.80 | Partial refund |
| N4567 | cust_1014 | processing | $445.00 | Bulk order |
| O8901 | cust_1015 | delivered | $12.99 | Loyalty member |
| P2345 | cust_1016 | shipped | $289.00 | Warranty claim |

**Policy documents (9 policies):**

| Policy | Description |
|--------|-------------|
| `refund_policy.md` | Refund eligibility, 30-day window, $500+ approval |
| `shipping_policy.md` | Shipping options, tracking, lost packages |
| `privacy_policy.md` | Data handling, PII protection, agent access limits |
| `warranty_policy.md` | Warranty coverage, claim process |
| `return_policy.md` | Return eligibility, conditions, timeframes |
| `account_security_policy.md` | Account verification, fraud protection |
| `loyalty_policy.md` | Loyalty program rules, rewards |
| `complaint_policy.md` | Complaint handling, escalation |
| `product_safety_policy.md` | Product safety, recalls, incident reporting |

---

## What's Next

| Step | Module | Status |
|------|--------|--------|
| 4 | Supporting modules (tools, RAG, governance) | ✅ Done |
| 5 | Strict Human Gate enforcement | ✅ Done |
| 6 | FastAPI backend (`app/main.py`) | ✅ Done |
| 7 | Streamlit UI (`ui.py`) | ✅ Done |
| 8 | Evaluation suite (`eval_suite.py`) | ✅ Done |

---

## Running Tests

### Unit & Integration Tests

```powershell
.\venv\Scripts\Activate.ps1
pytest tests/ -v
```

Current coverage:

| Test file | What it covers |
|-----------|----------------|
| `test_agent.py` | LangGraph planner, human gate, tool executor, audit log |
| `test_tools.py` | Mock order lookup |
| `test_support_tools.py` | Support tools (refund limits, goodwill credit) |
| `test_rag.py` | Policy retrieval from ChromaDB |
| `test_governance.py` | Audit logging + PII/compliance checks |
| `test_api.py` | FastAPI `/chat`, `/approve`, `/get_audit_log` |

### E2E Browser Tests (Playwright)

```powershell
# Install Playwright (one-time)
.\venv\Scripts\python.exe -m pip install playwright pytest-playwright
python -m playwright install chromium

# Start Streamlit (separate terminal)
streamlit run ui.py

# Run E2E tests
pytest tests/test_e2e.py -v
```

E2E test coverage:

| Test class | Tests | What it covers |
|------------|-------|----------------|
| `TestPageLoad` | 5 | Page loads, header, metrics, workflow graph, sidebar agents |
| `TestChatInput` | 2 | Chat input exists, can type message |
| `TestOrderLookup` | 3 | Orders A4821, C1234, B9999 lookup via chat |
| `TestRefundFlow` | 2 | Small ($5) and large ($300) refund requests |
| `TestGeneralInquiry` | 1 | General greeting / conversation |
| `TestDemoButtons` | 1 | All 5 demo buttons present |

### 8-Dimension Evaluation Suite

```powershell
# Run all 54 eval tests across 8 dimensions
pytest tests/test_eval_dimensions.py -v

# Generate JSON report
python -m tests.test_eval_dimensions
# writes eval_dimensions_report.json
```

| # | Dimension | Tests | What it validates |
|---|-----------|-------|-------------------|
| 1 | Intent Classification Accuracy | 9 | Correct intent detection (order_status, refund, general, out_of_scope) |
| 2 | Order Lookup Accuracy | 7 | Correct order details, missing orders, cancelled/processing status |
| 3 | Refund Governance | 8 | Small auto-approved, large gated, threshold boundary, policy cited |
| 4 | Policy RAG Retrieval | 5 | Policies retrieved for all query types, snippets logged |
| 5 | Risk Detection & Escalation | 6 | Legal threats, high-value refunds, adversarial prompts detected |
| 6 | Human-in-the-Loop (HITL) | 6 | Gate pauses for high-risk, not triggered for safe requests |
| 7 | Out-of-Scope Refusal | 6 | Competitor comparisons refused, no tools executed, polite message |
| 8 | Compliance & PII Protection | 7 | No credit cards leaked, compliance checks run, audit trail complete |

---

## Environment Variables

See [`.env.example`](.env.example) for the full list:

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub PAT for LLM (GPT-4o-mini via GitHub Models) + embedding fallback |
| `OPENAI_API_KEY` | No | OpenRouter or OpenAI key for LLM/embedding fallback |
| `GOOGLE_API_KEY` | No | Google Gemini embeddings (free tier, 1500 req/day) |
| `CHROMA_PERSIST_DIR` | No | ChromaDB storage path (default: `./data/chroma_db`) |
| `EMBEDDING_MODEL` | No | Embedding model name (default: `text-embedding-3-small`) |
| `OPENAI_MODEL` | No | LLM model name (default: `gpt-4o-mini`) |
| `AUDIT_LOG_PATH` | No | Audit log file path (default: `data/audit_log.json`) |

---

## Author

**Sriharshitha** — Capstone Project, 2026
