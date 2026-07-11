"""
Agent state schema for the Customer Support Resolution Agent.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """LangGraph state passed between planner, human gate, and tool executor nodes."""

    messages: Annotated[list[BaseMessage], add_messages]
    order_id: str
    refund_amount: float
    requires_human_approval: bool
    audit_log: list[dict]
