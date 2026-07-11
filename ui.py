"""
Standalone Streamlit demo for the Customer Support Resolution Agent.

Imports the LangGraph agent directly (no FastAPI required for the demo).
Run with: streamlit run ui.py
"""

from __future__ import annotations

import uuid

import streamlit as st

from app.agent.graph import format_agent_result, invoke_agent, resume_human_gate
from app.governance.audit import get_recent_audit_logs

st.set_page_config(
    page_title="Support Resolution Agent",
    page_icon="🛟",
    layout="wide",
)

st.markdown(
    """
    <style>
    .approval-box {
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #b91c1c;
        background-color: #fef2f2;
        color: #7f1d1d;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_session() -> None:
    defaults = {
        "session_id": str(uuid.uuid4()),
        "messages": [],
        "awaiting_approval": False,
        "gate_reason": "",
        "show_audit": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _append_message(role: str, content: str) -> None:
    st.session_state.messages.append({"role": role, "content": content})


def _handle_agent_state(state: dict) -> None:
    payload = format_agent_result(state)
    response = payload["response"]

    if payload["status"] == "WAITING_APPROVAL":
        reason = payload["gate_response"].get(
            "reason", "High value refund or legal threat detected."
        )
        st.session_state.awaiting_approval = True
        st.session_state.gate_reason = reason
        _append_message(
            "assistant",
            f"WAITING_APPROVAL: {reason}",
        )
        return

    st.session_state.awaiting_approval = False
    st.session_state.gate_reason = ""
    if response:
        _append_message("assistant", response)


def _run_chat_turn(user_message: str) -> None:
    _append_message("user", user_message)
    state = invoke_agent(user_message, thread_id=st.session_state.session_id)
    _handle_agent_state(state)


def _run_approval(decision: str) -> None:
    state = resume_human_gate(decision, thread_id=st.session_state.session_id)
    st.session_state.awaiting_approval = False
    st.session_state.gate_reason = ""
    _handle_agent_state(state)


_init_session()

st.title("Customer Support Resolution Agent")
st.caption("Capstone demo — LangGraph agent with human-in-the-loop governance")

with st.sidebar:
    st.subheader("Session")
    st.text_input("Session ID", value=st.session_state.session_id, disabled=True)
    if st.button("New Session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.awaiting_approval = False
        st.session_state.gate_reason = ""
        st.session_state.show_audit = False
        st.rerun()

    st.divider()
    st.subheader("Governance Demo")
    if st.button("View Audit Log"):
        st.session_state.show_audit = not st.session_state.show_audit

    if st.session_state.show_audit:
        events = get_recent_audit_logs(10)
        if events:
            st.json(events)
        else:
            st.info("No audit events recorded yet.")

    st.divider()
    st.markdown("**Try these examples:**")
    st.markdown("- `What is the status of order C1234?`")
    st.markdown("- `I want a refund of $5 for C1234`")
    st.markdown("- `Refund $25 for B9999`")
    st.markdown("- `I will sue you, refund order A4821`")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if st.session_state.awaiting_approval:
    reason = st.session_state.gate_reason or "High value refund or legal threat detected."
    st.markdown(
        f'<div class="approval-box">⚠️ Human Approval Required: {reason}</div>',
        unsafe_allow_html=True,
    )
    approve_col, reject_col = st.columns(2)
    with approve_col:
        if st.button("Approve", type="primary", key="approve_btn"):
            _run_approval("approve")
            st.rerun()
    with reject_col:
        if st.button("Reject", key="reject_btn"):
            _run_approval("reject")
            st.rerun()

if not st.session_state.awaiting_approval:
    prompt = st.chat_input("Describe your support issue...")
    if prompt:
        _run_chat_turn(prompt)
        st.rerun()
else:
    st.info("Approve or reject the pending request to continue chatting.")
