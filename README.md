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
├── app.py                  # FastAPI backend (placeholder)
├── ui.py                   # Streamlit frontend (placeholder)
├── eval_suite.py           # Evaluation script (placeholder)
├── requirements.txt        # Python dependencies
├── setup.ps1 / setup.sh    # Virtual environment setup
├── .env.example            # Environment variable template
├── app/
│   ├── agent/              # LangGraph state, nodes, graph
│   ├── tools/              # Order lookup, refund, human gate
│   ├── rag/                # Vector store & policy ingestion
│   └── governance/         # Audit logging & refusal logic
├── tests/                  # Pytest test suite
└── data/
    ├── orders/             # Mock order database
    └── policies/           # Support policy documents
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

### 4. Run the app (coming soon)

```powershell
uvicorn app:app --reload          # API on :8000
streamlit run ui.py               # UI on :8501
```

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
User message → Planner → [Human Gate | Tool Executor] → Response
```

**Escalation rules (enforced by Planner):**

- Refund amount **> $10** → requires human approval; refund tool blocked until approved
- Keywords **sue / lawyer / complaint** → requires human approval
- Order status queries → `check_order_status()`
- Small refunds (≤ $10) → `apply_refund()` after policy retrieval
- Late orders (≥ 3 days) → `send_goodwill_credit()` when no amount specified

**Usage example:**

```python
from app.agent import invoke_agent, resume_agent

# Normal flow
result = invoke_agent("What is my order status for C1234?", thread_id="session-1")

# High-value refund — pauses at human gate
result = invoke_agent("Refund $25 for B9999", thread_id="session-2")
if "__interrupt__" in result:
    resumed = resume_agent({"approved": True}, thread_id="session-2")
```

### Step 4 — Supporting modules & real integrations ✅

| Module | File | Description |
|--------|------|-------------|
| Mock orders | `data/mock_orders.py` | 5 fake orders (A4821 late, B9999 high-value, C1234 normal, +2 more); `lookup_order()` |
| Support tools | `app/tools/support_tools.py` | `check_order_status`, `apply_refund` (≤ $10 only), `send_goodwill_credit` |
| Policy RAG | `app/rag/policy_retriever.py` | `CharacterTextSplitter` + `InMemoryVectorStore` over `data/policies.txt` |
| Governance | `app/governance/audit.py` | `log_event()` persists every agent step to `data/audit_log.json` |
| Agent graph | `app/agent/graph.py` | Updated to call real tools, policy retriever, and audit logger |

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
| 5 | FastAPI backend (`app.py`) | 🔲 Pending |
| 6 | Streamlit UI (`ui.py`) | 🔲 Pending |
| 7 | Evaluation suite (`eval_suite.py`) | 🔲 Pending |

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
| `test_api.py` | FastAPI endpoints (placeholder) |

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
