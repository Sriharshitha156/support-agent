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
| RAG / vector store | ChromaDB |
| Validation | Pydantic |
| Testing | Pytest |

---

## Project Structure

```
support-agent/
├── app.py                      # FastAPI backend (placeholder)
├── ui.py                       # Streamlit frontend (placeholder)
├── eval_suite.py               # Evaluation script (placeholder)
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest config (pythonpath)
├── setup.ps1 / setup.sh        # Virtual environment setup
├── .env.example                # Environment variable template
├── app/
│   ├── agent/
│   │   ├── state.py            # AgentState schema
│   │   ├── nodes.py            # Node placeholders
│   │   └── graph.py            # LangGraph planner, human gate, tool executor
│   ├── tools/
│   │   ├── support_tools.py    # check_order_status, apply_refund, goodwill credit
│   │   ├── order_lookup.py     # (placeholder)
│   │   ├── refund_tool.py      # (placeholder)
│   │   └── human_gate.py       # (placeholder)
│   ├── rag/
│   │   ├── policy_retriever.py # Policy RAG (InMemoryVectorStore)
│   │   ├── vectorstore.py      # (placeholder)
│   │   └── ingestion.py        # (placeholder)
│   └── governance/
│       ├── audit.py            # log_event() → data/audit_log.json
│       └── refusal.py          # (placeholder)
├── tests/
│   ├── test_agent.py           # LangGraph integration tests
│   ├── test_support_tools.py   # Support tool unit tests
│   ├── test_tools.py           # Mock order lookup tests
│   ├── test_rag.py             # Policy retrieval tests
│   ├── test_governance.py      # Audit logging tests
│   └── test_api.py             # (placeholder)
└── data/
    ├── mock_orders.py          # 5 fake orders + lookup_order()
    ├── policies.txt            # 3 policies for RAG retrieval
    ├── orders/
    │   └── mock_orders.json    # Legacy sample orders
    └── policies/
        ├── refund_policy.md
        ├── shipping_policy.md
        └── privacy_policy.md
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

Edit `.env` and set your `OPENAI_API_KEY`.

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
| Planner node | ✅ Done | Keyword-based intent detection; routes to order lookup or policy check |
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

### Step 7 — Streamlit UI ✅

Standalone chat app (`streamlit run ui.py`) that imports the agent graph directly:

- Chat interface with `st.chat_input`
- Red **Human Approval Required** box when `WAITING_APPROVAL`
- **Approve** / **Reject** buttons call `resume_human_gate()`
- Sidebar **View Audit Log** for governance demo

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

**Mock order scenarios:**

| Order ID | Scenario |
|----------|----------|
| A4821 | Late delivery (5 days late) |
| B9999 | High value ($500) |
| C1234 | Normal shipped status |
| D5678 | Processing |
| E9012 | Cancelled |

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

```powershell
pytest tests/ -v
```

Current coverage:

| Test file | What it covers |
|-----------|----------------|
| `test_agent.py` | LangGraph planner, human gate, tool executor, audit log |
| `test_tools.py` | Mock order lookup |
| `test_support_tools.py` | Support tools (refund limits, goodwill credit) |
| `test_rag.py` | Policy retrieval |
| `test_governance.py` | Audit file logging |
| `test_api.py` | FastAPI `/chat`, `/approve`, `/get_audit_log` |

---

## Environment Variables

See [`.env.example`](.env.example) for the full list. Minimum required:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for LLM calls |
| `LANGCHAIN_API_KEY` | No | LangSmith tracing (optional) |
| `CHROMA_PERSIST_DIR` | No | ChromaDB storage path (default: `./data/chroma_db`) |

---

## Author

**Sriharshitha** — Capstone Project, 2026
