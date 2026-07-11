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
- Order status queries → `mock_order_lookup()`
- Small refunds (≤ $10) → `mock_policy_check()` without human gate

**Usage example:**

```python
from app.agent import invoke_agent, resume_agent

# Normal flow
result = invoke_agent("What is my order status for ORD-1001?", thread_id="session-1")

# High-value refund — pauses at human gate
result = invoke_agent("Refund $25 for ORD-1001", thread_id="session-2")
if "__interrupt__" in result:
    resumed = resume_agent({"approved": True}, thread_id="session-2")
```

---

## What's Next

| Step | Module | Status |
|------|--------|--------|
| 4 | Real tool implementations (`app/tools/`) | 🔲 Pending |
| 5 | RAG pipeline (`app/rag/`) | 🔲 Pending |
| 6 | Governance layer (`app/governance/`) | 🔲 Pending |
| 7 | FastAPI backend (`app.py`) | 🔲 Pending |
| 8 | Streamlit UI (`ui.py`) | 🔲 Pending |
| 9 | Evaluation suite (`eval_suite.py`) | 🔲 Pending |

---

## Running Tests

```powershell
pytest tests/ -v
```

Current coverage:

| Test file | What it covers |
|-----------|----------------|
| `test_agent.py` | LangGraph planner, human gate, tool executor, audit log |
| `test_tools.py` | Tool layer (placeholder) |
| `test_rag.py` | RAG pipeline (placeholder) |
| `test_governance.py` | Governance layer (placeholder) |
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
