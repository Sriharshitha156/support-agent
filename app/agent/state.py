"""
Agent state schema for the Customer Support Resolution Agent.
"""

from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """LangGraph state passed between preprocess, planner, human gate, and tool executor."""

    messages: Annotated[list[BaseMessage], add_messages]
    order_id: str
    refund_amount: float
    requires_human_approval: bool
    audit_log: list[dict]
    gate_response: NotRequired[dict]
    approval_status: NotRequired[str]
    detected_risk_keywords: NotRequired[list[str]]
