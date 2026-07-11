"""
LangGraph graph definition and compilation.

Wires together nodes from `nodes.py` with conditional edges for:

- tool routing (order lookup vs refund vs human escalation)
- governance refusal short-circuit
- end-of-turn response delivery

Exports a compiled `graph` object consumable by FastAPI and eval_suite.
"""
