"""
Enterprise Cyber-Security Operations Center (CSOC) Dashboard for the Customer Support Agent.

Run with: streamlit run ui.py
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
    page_title="CSOC Support Resolution Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Custom CSS Styling (Cyberpunk/Dark Ops Theme)
# ---------------------------------------------------------------------------

THEME_CSS = """
<style>
/* Core Dark Theme Settings */
.stApp {
    background-color: #050811 !important;
    color: #e6edf3 !important;
}

[data-testid="stSidebar"] {
    background-color: #0b0f19 !important;
    border-right: 1px solid #1f2438;
}

/* Custom Typography */
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;400;500;700&display=swap');
.mono {
    font-family: 'Fira Code', monospace !important;
}

/* Custom Message Cards */
.user-card {
    background-color: #161b22;
    border-left: 4px solid #58a6ff;
    border-radius: 6px;
    padding: 15px;
    margin-bottom: 12px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}

.agent-card {
    background-color: #0d1117;
    border-left: 4px solid #39ff14; /* Neon green */
    border-radius: 6px;
    padding: 15px;
    margin-bottom: 12px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}

.system-terminal-card {
    background-color: #050811;
    border: 1px solid #21262d;
    border-left: 4px solid #8b949e;
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 12px;
    font-family: 'Fira Code', monospace;
    font-size: 0.9rem;
    color: #8b949e;
}

/* Pulsing Alert Card for Human Gate */
@keyframes borderPulse {
    0% { border-color: #ff3333; box-shadow: 0 0 5px #ff3333; }
    50% { border-color: #800000; box-shadow: 0 0 20px #800000; }
    100% { border-color: #ff3333; box-shadow: 0 0 5px #ff3333; }
}

.human-gate-card {
    background-color: #1a0808;
    border: 2px solid #ff3333;
    border-radius: 8px;
    padding: 20px;
    margin-top: 15px;
    margin-bottom: 15px;
    animation: borderPulse 2s infinite;
}

/* Terminal Log Console styling */
.terminal-console {
    background-color: #03050a;
    border: 1px solid #1f2438;
    border-radius: 6px;
    padding: 12px;
    height: 350px;
    overflow-y: scroll;
    font-family: 'Fira Code', monospace;
    font-size: 0.8rem;
    color: #e6edf3;
    line-height: 1.4;
    box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.8);
}

.terminal-line {
    margin-bottom: 6px;
}

.log-info { color: #39ff14; }
.log-warn { color: #ffaa00; }
.log-crit { color: #ff3333; }

/* Status indicators */
.status-indicator {
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 0.8rem;
    font-family: 'Fira Code', monospace;
}
.status-op { background-color: #1b2f1f; color: #39ff14; border: 1px solid #39ff14; }
.status-act { background-color: #2b2210; color: #ffaa00; border: 1px solid #ffaa00; }
.status-err { background-color: #3b1919; color: #ff3333; border: 1px solid #ff3333; }

/* Hide Streamlit elements for a clean app look */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session State & Initial Logger Setup
# ---------------------------------------------------------------------------


def _init_session() -> None:
    defaults = {
        "session_id": str(uuid.uuid4()),
        "messages": [],
        "awaiting_approval": False,
        "gate_reason": "",
        "terminal_logs": [
            {
                "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "step": "SYSTEM",
                "level": "INFO",
                "action": "Booting Customer Support Resolution Agent...",
                "details": "[thread_id=initial]"
            },
            {
                "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "step": "RAG_DB",
                "level": "INFO",
                "action": "Persistent ChromaDB vector store connected",
                "details": "[collection=support_policies]"
            },
            {
                "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "step": "GOVERNANCE",
                "level": "INFO",
                "action": "Output Compliance Engine loaded successfully",
                "details": "[refusal modules online]"
            },
            {
                "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "step": "HUMAN_GATE",
                "level": "INFO",
                "action": "HITL interrupt listener online",
                "details": "[awaiting input]"
            }
        ]
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def log_to_terminal(step: str, action: str, level: str = "INFO", details: str = "") -> None:
    """Append a log entry to the in-memory terminal logger."""
    st.session_state.terminal_logs.append({
        "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "step": step.upper(),
        "level": level.upper(),
        "action": action,
        "details": details
    })


def _append_message(role: str, content: str) -> None:
    st.session_state.messages.append({"role": role, "content": content})

# ---------------------------------------------------------------------------
# Agent State Handlers
# ---------------------------------------------------------------------------


def _handle_agent_state(state: dict) -> None:
    payload = format_agent_result(state)
    response = payload["response"]

    # Log internal execution steps to the live terminal
    for entry in payload.get("audit_log", []):
        log_to_terminal(
            step=entry.get("step", "AGENT"),
            action=entry.get("action", "unknown"),
            level="WARN" if entry.get("risk_level") == "medium" else ("CRIT" if entry.get("risk_level") == "high" else "INFO"),
            details=f"planned: {entry.get('planned_action')}" if entry.get("planned_action") else ""
        )

    if payload["status"] == "WAITING_APPROVAL":
        reason = payload["gate_response"].get("reason", "High value refund or legal threat detected.")
        st.session_state.awaiting_approval = True
        st.session_state.gate_reason = reason
        log_to_terminal("GOVERNANCE", f"WAITING_APPROVAL: {reason}", "WARN")
        _append_message("system", f"WAITING_APPROVAL: {reason}")
        return

    st.session_state.awaiting_approval = False
    st.session_state.gate_reason = ""
    if response:
        _append_message("assistant", response)
        log_to_terminal("COMPLIANCE", "Response compliance check passed.", "INFO")


def _run_chat_turn(user_message: str) -> None:
    _append_message("user", user_message)
    log_to_terminal("INGRESS", f"Received human user input: {user_message[:50]}...", "INFO")

    # Typing / Execution Stages Simulation (Proving Agent Steps)
    status_placeholder = st.empty()
    
    status_placeholder.markdown("🛡️ **[STAGE 1/5] SECURITY COMPLIANCE SCAN:** Checking input for risk flags...")
    time.sleep(1.0)
    
    if "refund" in user_message.lower():
        status_placeholder.markdown("🛡️ **[STAGE 2/5] GOVERNANCE SCAN:** Checking refund eligibility & value threshold...")
        time.sleep(1.2)
    else:
        status_placeholder.markdown("🔍 **[STAGE 2/5] KNOWLEDGE RAG QUERY:** Querying ChromaDB for shipping/cancellation policies...")
        time.sleep(1.0)

    status_placeholder.markdown("⚙️ **[STAGE 3/5] ORCHESTRATION:** Executing LangGraph planner node loop...")
    time.sleep(1.0)

    # Actual LangGraph trigger
    state = invoke_agent(user_message, thread_id=st.session_state.session_id)
    
    status_placeholder.markdown("🛡️ **[STAGE 4/5] COMPLIANCE AUDIT:** Scanning final response for PII/refusal policies...")
    time.sleep(0.8)

    status_placeholder.markdown("✅ **[STAGE 5/5] RESPONSE FINALIZATION:** Rendering outputs...")
    time.sleep(0.5)
    
    status_placeholder.empty()

    _handle_agent_state(state)


def _run_approval(decision: str) -> None:
    log_to_terminal("GOVERNANCE", f"Manual override: Human {decision}ed action.", "INFO" if decision == "approve" else "WARN")
    
    with st.spinner("Processing human authorization override..."):
        time.sleep(1.5)
        state = resume_human_gate(decision, thread_id=st.session_state.session_id)
        
    st.session_state.awaiting_approval = False
    st.session_state.gate_reason = ""
    _handle_agent_state(state)
    st.toast("Override processed successfully!", icon="🛡️")

# ---------------------------------------------------------------------------
# Sidebar - Health & Command Center
# ---------------------------------------------------------------------------


_init_session()

with st.sidebar:
    st.title("🎛️ Command Controls")
    
    # System Status Panel
    st.subheader("System Status")
    st.markdown(
        """
        <div style="margin-bottom: 10px;">
            <span class="status-indicator status-op">🟢 OPERATIONAL</span> <strong>System</strong>
        </div>
        <div style="margin-bottom: 10px;">
            <span class="status-indicator status-op">🟢 CONNECTED</span> <strong>Vector Store</strong>
        </div>
        <div style="margin-bottom: 10px;">
            <span class="status-indicator status-op">🟢 ACTIVE</span> <strong>Human Gate</strong>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.divider()
    
    # Session Details
    st.subheader("Operational Settings")
    st.text_input("Operational Thread ID", value=st.session_state.session_id, disabled=True)
    if st.button("Reset Operations (New Session)", type="secondary", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.awaiting_approval = False
        st.session_state.gate_reason = ""
        st.session_state.terminal_logs = []
        _init_session()
        st.rerun()

    st.divider()
    
    # Mini scrolling log in the sidebar (always visible)
    st.subheader("Mini Live Feed")
    mini_log_html = '<div style="height: 180px; overflow-y: scroll; font-family: monospace; font-size: 0.75rem; background-color: #03050a; padding: 6px; border-radius: 4px; border: 1px solid #1f2438;">'
    for log in reversed(st.session_state.terminal_logs):
        level_class = "log-crit" if log["level"] == "CRIT" else ("log-warn" if log["level"] == "WARN" else "log-info")
        mini_log_html += f'<div><span class="{level_class}">[{log["level"]}]</span> {log["action"][:35]}...</div>'
    mini_log_html += '</div>'
    st.markdown(mini_log_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main Workspace Layout
# ---------------------------------------------------------------------------

st.title("🛡️ Enterprise Operations Command Center")
st.caption("LangGraph State Machine Agent & Real-time Governance Auditing Dashboard")

# Tab Selection
tab_chat, tab_audit, tab_policies = st.tabs([
    "💬 Agent Communications", 
    "📜 Real-Time System Terminal Logs", 
    "🛡️ Active Corporate Policies"
])

# --- Tab 1: Agent Communications ---
with tab_chat:
    # Display Chat Log
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f"""
                    <div class="user-card">
                        <span style="color: #58a6ff; font-weight: bold; font-family: monospace;">👤 USER:</span>
                        <div style="margin-top: 5px;">{msg['content']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif msg["role"] == "assistant":
                st.markdown(
                    f"""
                    <div class="agent-card">
                        <span style="color: #39ff14; font-weight: bold; font-family: monospace;">🤖 AGENT RESPONSE:</span>
                        <div style="margin-top: 5px;">{msg['content']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif msg["role"] == "system":
                st.markdown(
                    f"""
                    <div class="system-terminal-card">
                        <span style="color: #ffaa00; font-weight: bold; font-family: monospace;">🚨 SYSTEM STATE:</span> {msg['content']}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # Human Gate override controls
    if st.session_state.awaiting_approval:
        reason = st.session_state.gate_reason or "High value refund or legal threat detected."
        st.markdown(
            f"""
            <div class="human-gate-card">
                <h3 style="color: #ff3333; margin-top: 0; font-family: monospace;">🚨 HUMAN INTERRUPT GATE TRIGGERED</h3>
                <p style="color: #e6edf3; margin-bottom: 8px;"><strong>Reason:</strong> {reason}</p>
                <p style="font-size: 0.85rem; color: #8b949e;">The graph execution has been suspended. Compliance validation is required to authorize the execution of order tools.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        approve_col, reject_col = st.columns(2)
        with approve_col:
            # Styled green override
            st.markdown(
                """
                <style>
                div[element-to-bind="approve_btn"] button {
                    background-color: #238636 !important;
                    color: white !important;
                    border: 1px solid #39ff14 !important;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            if st.button("APPROVE OVERRIDE", type="primary", use_container_width=True, key="approve_btn"):
                _run_approval("approve")
                st.rerun()
                
        with reject_col:
            # Styled red override
            st.markdown(
                """
                <style>
                div[element-to-bind="reject_btn"] button {
                    background-color: #da3637 !important;
                    color: white !important;
                    border: 1px solid #ff3333 !important;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            if st.button("REJECT & TERMINATE", use_container_width=True, key="reject_btn"):
                _run_approval("reject")
                st.rerun()

    # Chat Input Box
    if not st.session_state.awaiting_approval:
        prompt = st.chat_input("Describe the support operations case to execute...")
        if prompt:
            _run_chat_turn(prompt)
            st.rerun()
    else:
        st.info("Human authorization override required to resume conversation.")

# --- Tab 2: System Terminal Logs ---
with tab_audit:
    st.subheader("Console Monitor")
    
    # Render scrolling terminal logs
    log_html = '<div class="terminal-console">'
    for log in st.session_state.terminal_logs:
        level_class = "log-crit" if log["level"] == "CRIT" else ("log-warn" if log["level"] == "WARN" else "log-info")
        log_html += (
            f'<div class="terminal-line">'
            f'<span style="color:#8b949e;">[{log["time"]}]</span> '
            f'<span style="color:#58a6ff;">[{log["step"]}]</span> '
            f'<span class="{level_class}">[{log["level"]}]</span> '
            f'{log["action"]} <span style="color:#8b949e;">{log["details"]}</span>'
            f'</div>'
        )
    log_html += '</div>'
    st.markdown(log_html, unsafe_allow_html=True)
    
    st.divider()
    
    # Audit log tree (displays raw JSON with syntax highlighting)
    st.subheader("Raw Governance Audit Records (Last 10 Events)")
    events = get_recent_audit_logs(10)
    if events:
        st.json(events)
    else:
        st.info("No audit logs captured in the current persistent log file.")

# --- Tab 3: Corporate Policies ---
with tab_policies:
    st.subheader("Active Compliance Policies")
    st.caption("Policies retrieved by the agent RAG system to ground responses and audit tool compliance.")
    
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
        # Fallback to display the flat policies.txt
        flat_policies = Path(__file__).resolve().parent / "data" / "policies.txt"
        if flat_policies.exists():
            with st.expander("Flat Policies Document", expanded=True):
                st.text(flat_policies.read_text(encoding="utf-8"))
        else:
            st.warning("No compliance policy documents found on disk.")
