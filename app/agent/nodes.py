"""
LangGraph node functions for the support agent workflow.

Each node is a pure function (state -> state) or async callable registered
on the graph. Planned nodes:

- classify_intent: determine what the customer is asking for
- retrieve_policy: RAG lookup against support policy documents
- call_tools: invoke order lookup, refund, or human-gate tools
- generate_response: LLM synthesis using context and tool results
- governance_check: run refusal / policy compliance before responding
"""
