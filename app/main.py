"""
FastAPI backend for the Customer Support Resolution Agent.

Run: uvicorn app.main:app --reload
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agent.graph import format_agent_result, invoke_agent, resume_human_gate
from app.governance.audit import get_recent_audit_logs

app = FastAPI(
    title="Customer Support Resolution Agent",
    description="LangGraph-powered support agent with human-in-the-loop governance.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)


class ApproveRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    decision: Literal["approve", "reject"]


class ChatResponse(BaseModel):
    session_id: str
    status: str
    response: str
    gate_response: dict
    requires_human_approval: bool
    approval_status: str = ""


class AuditLogResponse(BaseModel):
    events: list[dict]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Send a customer message and receive the agent response."""
    try:
        state = invoke_agent(request.message, thread_id=request.session_id)
    except Exception as exc:  # pragma: no cover - surfaced to client
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    payload = format_agent_result(state)
    return ChatResponse(
        session_id=request.session_id,
        status=payload["status"],
        response=payload["response"],
        gate_response=payload["gate_response"],
        requires_human_approval=payload["requires_human_approval"],
        approval_status=payload.get("approval_status", ""),
    )


@app.post("/approve", response_model=ChatResponse)
def approve(request: ApproveRequest) -> ChatResponse:
    """Resume a paused human gate with an approve/reject decision."""
    try:
        state = resume_human_gate(request.decision, thread_id=request.session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = format_agent_result(state)
    return ChatResponse(
        session_id=request.session_id,
        status=payload["status"],
        response=payload["response"],
        gate_response=payload["gate_response"],
        requires_human_approval=payload["requires_human_approval"],
        approval_status=payload.get("approval_status", ""),
    )


@app.get("/get_audit_log", response_model=AuditLogResponse)
def get_audit_log() -> AuditLogResponse:
    """Return the last 10 governance audit events."""
    return AuditLogResponse(events=get_recent_audit_logs(10))
