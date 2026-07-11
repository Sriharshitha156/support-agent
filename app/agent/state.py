"""
Agent state schema for the Customer Support Resolution Agent.

Defines the TypedDict / Pydantic model that flows through the LangGraph
workflow. Expected fields include:

- messages: conversation history between customer and agent
- customer_id: identifier for the requesting customer
- order_id: optional order under discussion
- intent: classified support intent (refund, status, policy, escalation)
- rag_context: retrieved policy snippets from the vector store
- tool_results: outputs from order lookup, refund, or human-gate tools
- requires_human: flag set when escalation is needed
- audit_trail: list of governance events for this session
"""
