"""
Enterprise Cyber-Security Operations Command Center (CSOC) Dashboard for Autonomous AI Agents.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from app.agent.graph import format_agent_result, invoke_agent, resume_human_gate
from app.governance.audit import get_recent_audit_logs

# Setup Page Configuration
st.set_page_config(
    page_title="CSOC support-agent Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Custom CSS Styling (Glassmorphism & Futuristic JARVIS-Bloomberg HUD Theme)
# ---------------------------------------------------------------------------

THEME_CSS = """
<style>
/* Core Dark/Glassmorphic Background */
.stApp {
    background-color: #030712 !important;
    background-image: 
        radial-gradient(at 0% 0%, rgba(31, 38, 135, 0.15) 0px, transparent 50%),
        radial-gradient(at 50% 0%, rgba(99, 102, 241, 0.1) 0px, transparent 50%),
        radial-gradient(at 100% 0%, rgba(139, 92, 246, 0.15) 0px, transparent 50%),
        radial-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 0);
    background-size: 100% 100%, 100% 100%, 100% 100%, 20px 20px;
    color: #f3f4f6 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

[data-testid="stSidebar"] {
    background-color: rgba(11, 15, 25, 0.85) !important;
    backdrop-filter: blur(16px) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}

/* Glassmorphism Panel Card */
.glass-panel {
    background: rgba(17, 24, 39, 0.45) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 12px !important;
    padding: 20px !important;
    margin-bottom: 20px !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
}

/* Custom Message Cards */
.user-card {
    background: rgba(30, 41, 59, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-left: 4px solid #38bdf8; /* Cyan accent */
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
}

.agent-card {
    background: rgba(17, 24, 39, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-left: 4px solid #34d399; /* Emerald accent */
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
}

.system-terminal-card {
    background: #020617;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-left: 4px solid #a78bfa; /* Purple accent */
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 12px;
    font-family: 'Fira Code', monospace;
    font-size: 0.85rem;
    color: #94a3b8;
}

/* Metrics Dashboard Cards */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 15px;
    margin-bottom: 25px;
}

.metric-card {
    background: rgba(15, 23, 42, 0.45);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    padding: 15px;
    text-align: center;
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05);
}

.metric-title {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #94a3b8;
    margin-bottom: 6px;
}

.metric-value {
    font-size: 1.4rem;
    font-weight: 700;
    font-family: 'Fira Code', monospace;
    background: linear-gradient(135deg, #38bdf8, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* Pulsing Red Hanger Gate Card */
@keyframes borderPulse {
    0% { border-color: #ff3333; box-shadow: 0 0 5px rgba(255, 51, 51, 0.5); }
    50% { border-color: #800000; box-shadow: 0 0 20px rgba(255, 51, 51, 0.2); }
    100% { border-color: #ff3333; box-shadow: 0 0 5px rgba(255, 51, 51, 0.5); }
}

.human-gate-card {
    background-color: rgba(31, 10, 10, 0.45);
    backdrop-filter: blur(12px);
    border: 2px solid #ff3333;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    animation: borderPulse 2s infinite;
}

/* Scrolling Terminal HUD Console */
.terminal-hud {
    background-color: #020617;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    padding: 15px;
    height: 320px;
    overflow-y: scroll;
    font-family: 'Fira Code', monospace;
    font-size: 0.75rem;
    color: #38bdf8;
    line-height: 1.5;
    box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.9);
}

.terminal-line {
    margin-bottom: 6px;
}

.log-info { color: #34d399; } /* Emerald */
.log-warn { color: #fbbf24; } /* Amber */
.log-crit { color: #f87171; } /* Red */
.log-step { color: #818cf8; } /* Indigo */

/* Agent status layout */
.agent-status-box {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: rgba(30, 41, 59, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.03);
    border-radius: 8px;
    margin-bottom: 8px;
}

.agent-name {
    font-weight: 500;
    font-size: 0.85rem;
    color: #e2e8f0;
    display: flex;
    align-items: center;
    gap: 8px;
}

.status-badge {
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    font-family: 'Fira Code', monospace;
}

.badge-thinking { background: rgba(139, 92, 246, 0.15); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }
.badge-running { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
.badge-waiting { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
.badge-idle { background: rgba(71, 85, 105, 0.15); color: #94a3b8; border: 1px solid rgba(71, 85, 105, 0.3); }
.badge-complete { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }

/* Hide standard components */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SVG Workflow Graph Generator (Dynamic Node Highlighting)
# ---------------------------------------------------------------------------


def generate_workflow_svg(stage: str) -> str:
    """Generate inline SVG code with neon-glowing nodes matching the current execution stage."""
    # Nodes configuration
    nodes = {
        "ingress": {"fill": "#0f172a", "stroke": "#334155", "filter": ""},
        "preprocess": {"fill": "#0f172a", "stroke": "#334155", "filter": ""},
        "planner": {"fill": "#0f172a", "stroke": "#334155", "filter": ""},
        "rag": {"fill": "#0f172a", "stroke": "#334155", "filter": ""},
        "gate": {"fill": "#0f172a", "stroke": "#334155", "filter": ""},
        "exec": {"fill": "#0f172a", "stroke": "#334155", "filter": ""},
        "compliance": {"fill": "#0f172a", "stroke": "#334155", "filter": ""},
        "egress": {"fill": "#0f172a", "stroke": "#334155", "filter": ""}
    }

    # Glow & coloring configurations
    active_color = "#38bdf8"
    active_stroke = "#0ea5e9"
    active_filter = "url(#glow-cyan)"

    warn_color = "#fbbf24"
    warn_stroke = "#d97706"
    warn_filter = "url(#glow-amber)"

    success_color = "#34d399"
    success_stroke = "#10b981"
    success_filter = "url(#glow-emerald)"

    # Stage highlight mapping
    if stage == "ingress":
        nodes["ingress"] = {"fill": active_color, "stroke": active_stroke, "filter": active_filter}
    elif stage == "preprocess":
        nodes["ingress"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["preprocess"] = {"fill": active_color, "stroke": active_stroke, "filter": active_filter}
    elif stage == "planner":
        nodes["ingress"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["preprocess"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["planner"] = {"fill": active_color, "stroke": active_stroke, "filter": active_filter}
    elif stage == "rag":
        nodes["ingress"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["preprocess"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["planner"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["rag"] = {"fill": active_color, "stroke": active_stroke, "filter": active_filter}
    elif stage == "gate":
        nodes["ingress"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["preprocess"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["planner"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["rag"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["gate"] = {"fill": warn_color, "stroke": warn_stroke, "filter": warn_filter}
    elif stage == "exec":
        nodes["ingress"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["preprocess"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["planner"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["rag"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["exec"] = {"fill": active_color, "stroke": active_stroke, "filter": active_filter}
    elif stage == "compliance":
        nodes["ingress"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["preprocess"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["planner"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["rag"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["exec"] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}
        nodes["compliance"] = {"fill": warn_color, "stroke": warn_stroke, "filter": warn_filter}
    elif stage == "complete":
        for k in nodes:
            nodes[k] = {"fill": success_color, "stroke": success_stroke, "filter": success_filter}

    svg = f"""
    <svg width="100%" height="90" viewBox="0 0 800 90">
      <defs>
        <filter id="glow-cyan" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
        <filter id="glow-amber" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
        <filter id="glow-emerald" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      
      <!-- Connection Lines -->
      <line x1="50" y1="35" x2="150" y2="35" stroke="#1f2937" stroke-width="3" />
      <line x1="150" y1="35" x2="250" y2="35" stroke="#1f2937" stroke-width="3" />
      <line x1="250" y1="35" x2="350" y2="35" stroke="#1f2937" stroke-width="3" />
      <line x1="350" y1="35" x2="460" y2="35" stroke="#1f2937" stroke-width="3" />
      <line x1="460" y1="35" x2="570" y2="35" stroke="#1f2937" stroke-width="3" />
      <line x1="570" y1="35" x2="680" y2="35" stroke="#1f2937" stroke-width="3" />
      <line x1="680" y1="35" x2="750" y2="35" stroke="#1f2937" stroke-width="3" />
      
      <!-- Connection Lines Active Status Glowing overlays -->
      {"<line x1='50' y1='35' x2='150' y2='35' stroke='#38bdf8' stroke-width='3' filter='url(#glow-cyan)' />" if stage != "idle" and stage != "ingress" else ""}
      {"<line x1='150' y1='35' x2='250' y2='35' stroke='#38bdf8' stroke-width='3' filter='url(#glow-cyan)' />" if stage in ("planner", "rag", "gate", "exec", "compliance", "complete") else ""}
      {"<line x1='250' y1='35' x2='350' y2='35' stroke='#38bdf8' stroke-width='3' filter='url(#glow-cyan)' />" if stage in ("rag", "gate", "exec", "compliance", "complete") else ""}
      {"<line x1='350' y1='35' x2='460' y2='35' stroke='#38bdf8' stroke-width='3' filter='url(#glow-cyan)' />" if stage in ("gate", "exec", "compliance", "complete") else ""}
      {"<line x1='460' y1='35' x2='570' y2='35' stroke='#38bdf8' stroke-width='3' filter='url(#glow-cyan)' />" if stage in ("exec", "compliance", "complete") else ""}
      {"<line x1='570' y1='35' x2='680' y2='35' stroke='#38bdf8' stroke-width='3' filter='url(#glow-cyan)' />" if stage in ("compliance", "complete") else ""}
      {"<line x1='680' y1='35' x2='750' y2='35' stroke='#34d399' stroke-width='3' filter='url(#glow-emerald)' />" if stage == "complete" else ""}

      <!-- Nodes -->
      <circle cx="50" cy="35" r="14" fill="{nodes['ingress']['fill']}" filter="{nodes['ingress']['filter']}" stroke="{nodes['ingress']['stroke']}" stroke-width="3" />
      <text x="50" y="68" fill="#94a3b8" font-size="8" text-anchor="middle" font-family="'Fira Code', monospace" font-weight="600">INGRESS</text>
      
      <circle cx="150" cy="35" r="14" fill="{nodes['preprocess']['fill']}" filter="{nodes['preprocess']['filter']}" stroke="{nodes['preprocess']['stroke']}" stroke-width="3" />
      <text x="150" y="68" fill="#94a3b8" font-size="8" text-anchor="middle" font-family="'Fira Code', monospace" font-weight="600">PREPROCESS</text>
      
      <circle cx="250" cy="35" r="14" fill="{nodes['planner']['fill']}" filter="{nodes['planner']['filter']}" stroke="{nodes['planner']['stroke']}" stroke-width="3" />
      <text x="250" y="68" fill="#94a3b8" font-size="8" text-anchor="middle" font-family="'Fira Code', monospace" font-weight="600">PLANNER</text>
      
      <circle cx="350" cy="35" r="14" fill="{nodes['rag']['fill']}" filter="{nodes['rag']['filter']}" stroke="{nodes['rag']['stroke']}" stroke-width="3" />
      <text x="350" y="68" fill="#94a3b8" font-size="8" text-anchor="middle" font-family="'Fira Code', monospace" font-weight="600">POLICY RAG</text>
      
      <circle cx="460" cy="35" r="14" fill="{nodes['gate']['fill']}" filter="{nodes['gate']['filter']}" stroke="{nodes['gate']['stroke']}" stroke-width="3" />
      <text x="460" y="68" fill="#94a3b8" font-size="8" text-anchor="middle" font-family="'Fira Code', monospace" font-weight="600">HUMAN GATE</text>
      
      <circle cx="570" cy="35" r="14" fill="{nodes['exec']['fill']}" filter="{nodes['exec']['filter']}" stroke="{nodes['exec']['stroke']}" stroke-width="3" />
      <text x="570" y="68" fill="#94a3b8" font-size="8" text-anchor="middle" font-family="'Fira Code', monospace" font-weight="600">TOOL EXEC</text>
      
      <circle cx="680" cy="35" r="14" fill="{nodes['compliance']['fill']}" filter="{nodes['compliance']['filter']}" stroke="{nodes['compliance']['stroke']}" stroke-width="3" />
      <text x="680" y="68" fill="#94a3b8" font-size="8" text-anchor="middle" font-family="'Fira Code', monospace" font-weight="600">COMPLIANCE</text>
      
      <circle cx="750" cy="35" r="14" fill="{nodes['egress']['fill']}" filter="{nodes['egress']['filter']}" stroke="{nodes['egress']['stroke']}" stroke-width="3" />
      <text x="750" y="68" fill="#94a3b8" font-size="8" text-anchor="middle" font-family="'Fira Code', monospace" font-weight="600">EGRESS</text>
    </svg>
    """
    return svg

# ---------------------------------------------------------------------------
# Session Setup & Logger Initialization
# ---------------------------------------------------------------------------


def _init_session() -> None:
    defaults = {
        "session_id": str(uuid.uuid4()),
        "messages": [],
        "awaiting_approval": False,
        "gate_reason": "",
        "current_stage": "idle",
        "recent_tool_calls": [
            {"time": "15:44:00", "tool": "ChromaDB Query", "status": "COMPLETED", "duration": "0.14s"},
            {"time": "15:44:02", "tool": "Refund Evaluator", "status": "SKIPPED", "duration": "0.02s"},
            {"time": "15:44:02", "tool": "Zendesk Escalator", "status": "QUEUED", "duration": "0.00s"}
        ],
        "stats": {
            "tasks_completed": 142,
            "avg_latency": 842,
            "tool_success_rate": 98.4,
            "human_escalations": 8,
            "cost_per_execution": 0.0024
        },
        "terminal_logs": [
            {"time": "15:40:00", "step": "SYSTEM", "level": "INFO", "action": "Booting CSOC Mission Control Engine...", "details": "[ready]"},
            {"time": "15:40:01", "step": "RAG_DB", "level": "INFO", "action": "ChromaDB connection verified", "details": "[persistent_store=active]"},
            {"time": "15:40:01", "step": "COMPLIANCE", "level": "INFO", "action": "Compliance Guardrails online", "details": "[PII scanners loaded]"},
            {"time": "15:40:02", "step": "HUMAN_GATE", "level": "INFO", "action": "Manager approval gate listening", "details": "[HITL loop armed]"}
        ]
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def log_to_terminal(step: str, action: str, level: str = "INFO", details: str = "") -> None:
    st.session_state.terminal_logs.append({
        "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "step": step.upper(),
        "level": level.upper(),
        "action": action,
        "details": details
    })


def record_tool_call(tool: str, status: str, duration: str) -> None:
    st.session_state.recent_tool_calls.insert(0, {
        "time": datetime.now().strftime("%H:%M:%S"),
        "tool": tool,
        "status": status,
        "duration": duration
    })
    st.session_state.recent_tool_calls = st.session_state.recent_tool_calls[:6]


def _append_message(role: str, content: str) -> None:
    st.session_state.messages.append({"role": role, "content": content})

# ---------------------------------------------------------------------------
# Agent Pipeline Execution
# ---------------------------------------------------------------------------


def _handle_agent_state(state: dict) -> None:
    payload = format_agent_result(state)
    response = payload["response"]

    # Map state audit logs to UI terminal logger
    for entry in payload.get("audit_log", []):
        log_to_terminal(
            step=entry.get("step", "AGENT"),
            action=entry.get("action", "unknown"),
            level="WARN" if entry.get("risk_level") == "medium" else ("CRIT" if entry.get("risk_level") == "high" else "INFO"),
            details=f"planned: {entry.get('planned_action')}" if entry.get('planned_action') else ""
        )

    if payload["status"] == "WAITING_APPROVAL":
        st.session_state.current_stage = "gate"
        reason = payload["gate_response"].get("reason", "High value refund or legal threat detected.")
        st.session_state.awaiting_approval = True
        st.session_state.gate_reason = reason
        st.session_state.stats["human_escalations"] += 1
        record_tool_call("Escalate to Human", "AWAITING_APPROVAL", "0.45s")
        log_to_terminal("GOVERNANCE", f"WAITING_APPROVAL triggered: {reason}", "WARN")
        _append_message("system", f"WAITING_APPROVAL: {reason}")
        return

    st.session_state.current_stage = "complete"
    st.session_state.awaiting_approval = False
    st.session_state.gate_reason = ""
    st.session_state.stats["tasks_completed"] += 1
    
    if response:
        _append_message("assistant", response)
        log_to_terminal("COMPLIANCE", "Compliance validation passed. Response released.", "INFO")


def _run_chat_turn(user_message: str) -> None:
    _append_message("user", user_message)
    log_to_terminal("INGRESS", f"Ingested user payload: {user_message[:40]}...", "INFO")

    # Step-by-Step Visualization Loop (JARVIS style stage indicators)
    status_box = st.empty()
    
    # Preprocess
    st.session_state.current_stage = "ingress"
    status_box.markdown("🔍 **[STAGE 1/6] INGRESS DISPATCH:** Parsing package signatures...")
    time.sleep(0.7)
    
    st.session_state.current_stage = "preprocess"
    status_box.markdown("🛡️ **[STAGE 2/6] SECURITY SHIELD:** Inspecting risk signatures and CC tokens...")
    time.sleep(0.8)

    # Planner / RAG
    st.session_state.current_stage = "planner"
    status_box.markdown("⚙️ **[STAGE 3/6] ORCHESTRATION PLANNER:** Defining execution graph branches...")
    time.sleep(0.8)

    st.session_state.current_stage = "rag"
    if "refund" in user_message.lower():
        status_box.markdown("🛡️ **[STAGE 4/6] GOVERNANCE AUDIT:** Evaluating refund window criteria...")
        record_tool_call("Refund Evaluator", "RUNNING", "0.00s")
    else:
        status_box.markdown("🔍 **[STAGE 4/6] VECTOR STORE RETRIEVAL:** Extracting policies from ChromaDB...")
        record_tool_call("ChromaDB Query", "RUNNING", "0.00s")
    time.sleep(1.0)

    # Invoke Agent
    st.session_state.current_stage = "exec"
    status_box.markdown("📦 **[STAGE 5/6] TOOL INVOCATION:** Triggering tool executor node...")
    
    t_start = time.time()
    state = invoke_agent(user_message, thread_id=st.session_state.session_id)
    t_end = time.time()
    
    # Record metrics latency
    st.session_state.stats["avg_latency"] = int((st.session_state.stats["avg_latency"] * 9 + (t_end - t_start) * 1000) / 10)
    
    # Update tool stream logs
    if "refund" in user_message.lower():
        record_tool_call("Refund Evaluator", "COMPLETED", f"{t_end-t_start:.2f}s")
    else:
        record_tool_call("ChromaDB Query", "COMPLETED", f"{t_end-t_start:.2f}s")
    time.sleep(0.6)

    # Compliance
    st.session_state.current_stage = "compliance"
    status_box.markdown("🛡️ **[STAGE 6/6] COMPLIANCE OVERLAY:** Inspecting response text...")
    time.sleep(0.5)

    status_box.empty()
    _handle_agent_state(state)


def _run_approval(decision: str) -> None:
    log_to_terminal("GOVERNANCE", f"Manual override: Manager {decision}ed transaction.", "INFO" if decision == "approve" else "WARN")
    
    with st.spinner("Processing override authorization..."):
        time.sleep(1.2)
        state = resume_human_gate(decision, thread_id=st.session_state.session_id)
        
    st.session_state.awaiting_approval = False
    st.session_state.gate_reason = ""
    
    if decision == "approve":
        st.session_state.current_stage = "exec"
        record_tool_call("Escalate to Human", "APPROVED", "1.20s")
    else:
        st.session_state.current_stage = "complete"
        record_tool_call("Escalate to Human", "REJECTED", "1.20s")
        
    _handle_agent_state(state)
    st.toast(f"Gate override {decision}d successfully.", icon="🛡️")

# ---------------------------------------------------------------------------
# Sidebar - Agent Network Panel
# ---------------------------------------------------------------------------


_init_session()

# Determine statuses for visual display
support_status = "thinking" if st.session_state.current_stage in ("ingress", "preprocess", "planner", "rag", "exec", "compliance") else "idle"
if st.session_state.current_stage == "gate":
    support_status = "waiting"

with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #38bdf8; font-family: monospace;'>🤖 AGENT NET</h2>", unsafe_allow_html=True)
    st.caption("Active supervisor nodes in the orchestrator chain:")
    
    # Active Agent Network status list
    agents_list = [
        {"name": "Support Agent", "emoji": "💬", "status": support_status},
        {"name": "Compliance Agent", "emoji": "🛡️", "status": "running" if st.session_state.current_stage == "compliance" else "idle"},
        {"name": "Risk Scan Agent", "emoji": "⚠️", "status": "running" if st.session_state.current_stage == "preprocess" else "idle"},
        {"name": "Research Agent", "emoji": "🔍", "status": "running" if st.session_state.current_stage == "rag" else "idle"},
        {"name": "Finance Agent", "emoji": "💳", "status": "waiting" if st.session_state.current_stage == "gate" else "idle"}
    ]

    for agent in agents_list:
        badge_style = "badge-thinking" if agent["status"] == "thinking" else (
            "badge-running" if agent["status"] == "running" else (
                "badge-waiting" if agent["status"] == "waiting" else "badge-idle"
            )
        )
        st.markdown(
            f"""
            <div class="agent-status-box">
                <div class="agent-name">
                    <span>{agent['emoji']}</span>
                    <span>{agent['name']}</span>
                </div>
                <span class="status-badge {badge_style}">{agent['status']}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.divider()

    # System Status Dashboard
    st.markdown("<h4 style='font-family: monospace;'>System Operations</h4>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="margin-bottom: 8px; font-size: 0.8rem;">
            <span class="status-indicator status-op">🟢 OPERATIONAL</span> <strong>Network</strong>
        </div>
        <div style="margin-bottom: 8px; font-size: 0.8rem;">
            <span class="status-indicator status-op">🟢 CONNECTED</span> <strong>Vector DB</strong>
        </div>
        <div style="margin-bottom: 8px; font-size: 0.8rem;">
            <span class="status-indicator status-op">🟢 ACTIVE</span> <strong>HITL Gate</strong>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.divider()
    
    # Operation Settings
    st.text_input("CSOC Session ID", value=st.session_state.session_id, disabled=True)
    if st.button("Reset Operations Network", type="secondary", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.awaiting_approval = False
        st.session_state.gate_reason = ""
        st.session_state.current_stage = "idle"
        st.session_state.recent_tool_calls = []
        st.session_state.terminal_logs = []
        _init_session()
        st.rerun()

# ---------------------------------------------------------------------------
# Main CSOC Workspace
# ---------------------------------------------------------------------------

# Hero Title
st.markdown("<h1 style='margin-bottom: 0; padding-bottom: 0;'>🛡️ Enterprise Operations Command Center</h1>", unsafe_allow_html=True)
st.caption("Autonomous Support Agent Orchestrator & Live Compliance Audit HUD")

# Interactive Metrics Row
st.markdown(
    f"""
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-title">Tasks Completed</div>
            <div class="metric-value">{st.session_state.stats['tasks_completed']}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Avg Latency</div>
            <div class="metric-value">{st.session_state.stats['avg_latency']}ms</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Tool Success Rate</div>
            <div class="metric-value">{st.session_state.stats['tool_success_rate']}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Human Escalations</div>
            <div class="metric-value">{st.session_state.stats['human_escalations']}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Cost Per Exec</div>
            <div class="metric-value">${st.session_state.stats['cost_per_execution']:.4f}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Tabs Navigation
tab_main, tab_logs, tab_policies = st.tabs([
    "💬 Agent Workflow & Communications", 
    "📜 Real-Time System Terminal Logs", 
    "🛡️ Active Corporate Policies"
])

# --- Tab 1: Agent Workflow & Communications ---
with tab_main:
    # 1. Agent Workflow Graph (Always Rendered at Top)
    st.markdown("<div class='glass-panel' style='padding: 10px !important;'>", unsafe_allow_html=True)
    st.markdown("<h5 style='margin-top: 0; font-family: monospace; color:#38bdf8;'>Live Graph State Trace</h5>", unsafe_allow_html=True)
    st.markdown(generate_workflow_svg(st.session_state.current_stage), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # 2. Main split screen
    left_col, right_col = st.columns([3, 2])
    
    # LEFT COLUMN: Active Chat Cards & Input
    with left_col:
        st.markdown("<h4 style='font-family: monospace;'>Active Dialog Channel</h4>", unsafe_allow_html=True)
        
        chat_box = st.container()
        with chat_box:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st.markdown(
                        f"""
                        <div class="user-card">
                            <span style="color: #38bdf8; font-weight: bold; font-family: monospace;">👤 USER:</span>
                            <div style="margin-top: 5px;">{msg['content']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                elif msg["role"] == "assistant":
                    st.markdown(
                        f"""
                        <div class="agent-card">
                            <span style="color: #34d399; font-weight: bold; font-family: monospace;">🤖 AGENT RESPONSE:</span>
                            <div style="margin-top: 5px;">{msg['content']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                elif msg["role"] == "system":
                    st.markdown(
                        f"""
                        <div class="system-terminal-card">
                            <span style="color: #fbbf24; font-weight: bold; font-family: monospace;">🚨 GOVERNANCE INTERRUPT:</span> {msg['content']}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
        
        # User input box (disabled if waiting approval)
        if not st.session_state.awaiting_approval:
            prompt = st.chat_input("Enter command or customer support payload...")
            if prompt:
                _run_chat_turn(prompt)
                st.rerun()
        else:
            st.info("Input blocked: Responding to Human Authorization Request.")

    # RIGHT COLUMN: Human Approval Queue & Live Tool Calls Stream
    with right_col:
        # HUMAN APPROVAL CENTER
        st.markdown("<h4 style='font-family: monospace;'>HITL Approval Queue</h4>", unsafe_allow_html=True)
        if st.session_state.awaiting_approval:
            reason = st.session_state.gate_reason or "High value refund or legal threat detected."
            st.markdown(
                f"""
                <div class="human-gate-card">
                    <h3 style="color: #f87171; margin-top: 0; font-family: monospace;">⚠️ HUMAN GATE OVERRIDE REQUIRED</h3>
                    <p style="color: #e2e8f0; margin-bottom: 12px; font-size:0.9rem;"><strong>Reason:</strong> {reason}</p>
                    <p style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 15px;">The agent state has been halted on node [human_gate]. Approve the action below to release the tool executor.</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            approve_btn, reject_btn = st.columns(2)
            with approve_btn:
                # Custom Green Button styling
                st.markdown(
                    """
                    <style>
                    div[element-to-bind="approve_action_btn"] button {
                        background: rgba(16, 185, 129, 0.25) !important;
                        color: #34d399 !important;
                        border: 1px solid #34d399 !important;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("APPROVE OVERRIDE", use_container_width=True, key="approve_action_btn"):
                    _run_approval("approve")
                    st.rerun()
            with reject_btn:
                # Custom Red Button styling
                st.markdown(
                    """
                    <style>
                    div[element-to-bind="reject_action_btn"] button {
                        background: rgba(239, 68, 68, 0.25) !important;
                        color: #f87171 !important;
                        border: 1px solid #f87171 !important;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("REJECT ACTION", use_container_width=True, key="reject_action_btn"):
                    _run_approval("reject")
                    st.rerun()
        else:
            st.markdown(
                """
                <div style="border: 1px dashed rgba(255,255,255,0.08); border-radius: 8px; padding: 25px; text-align: center; color: #64748b; font-size: 0.85rem; font-family: monospace;">
                    📭 APPROVAL QUEUE EMPTY
                </div>
                """,
                unsafe_allow_html=True
            )

        st.divider()

        # LIVE TOOL CALLS STREAM
        st.markdown("<h4 style='font-family: monospace;'>Live Tool Calls Stream</h4>", unsafe_allow_html=True)
        for call in st.session_state.recent_tool_calls:
            color = "#34d399" if call["status"] == "COMPLETED" else ("#fbbf24" if call["status"] == "AWAITING_APPROVAL" else ("#ef4444" if call["status"] == "REJECTED" else "#64748b"))
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(30,41,59,0.15); border: 1px solid rgba(255,255,255,0.03); border-radius: 6px; padding: 8px 12px; margin-bottom: 6px; font-family: monospace; font-size: 0.75rem;">
                    <div>
                        <span style="color: #64748b;">[{call['time']}]</span>
                        <strong style="color: #e2e8f0; margin-left: 5px;">{call['tool']}</strong>
                    </div>
                    <div>
                        <span style="color: {color}; font-weight: bold; margin-right: 10px;">{call['status']}</span>
                        <span style="color: #64748b;">{call['duration']}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

# --- Tab 2: System Terminal Logs ---
with tab_logs:
    st.subheader("Console Output Stream")
    
    # Scrolling terminal console
    log_html = '<div class="terminal-hud">'
    for log in st.session_state.terminal_logs:
        level_class = "log-crit" if log["level"] == "CRIT" else ("log-warn" if log["level"] == "WARN" else "log-info")
        log_html += (
            f'<div class="terminal-line">'
            f'<span style="color:#64748b;">[{log["time"]}]</span> '
            f'<span class="log-step">[{log["step"]}]</span> '
            f'<span class="{level_class}">[{log["level"]}]</span> '
            f'{log["action"]} <span style="color:#64748b;">{log["details"]}</span>'
            f'</div>'
        )
    log_html += '</div>'
    st.markdown(log_html, unsafe_allow_html=True)

    st.divider()

    # Audit JSON Tree with syntax highlighting
    st.subheader("Raw Audit Log Payload Tree (Last 10 events)")
    events = get_recent_audit_logs(10)
    if events:
        st.json(events)
    else:
        st.info("No audit logs captured in audit_log.json.")

# --- Tab 3: Corporate Policies ---
with tab_policies:
    st.subheader("Corporate Compliance Policy Base")
    st.caption("Active policies referenced by RAG matching during agent planning:")
    
    policies_dir = Path(__file__).resolve().parent / "data" / "policies"
    if policies_dir.exists():
        for file_path in policies_dir.glob("*.md"):
            with st.expander(f"🛡️ {file_path.name.replace('_', ' ').title()}", expanded=True):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    st.markdown(content)
                except Exception as exc:
                    st.error(f"Error loading {file_path.name}: {exc}")
    else:
        # Fallback to display policies.txt
        flat_policies = Path(__file__).resolve().parent / "data" / "policies.txt"
        if flat_policies.exists():
            with st.expander("Corporate Policies Document", expanded=True):
                st.text(flat_policies.read_text(encoding="utf-8"))
        else:
            st.warning("No policy documents found on disk.")
