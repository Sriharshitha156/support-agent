"""
Mock order lookup tool.

Queries the mock order database in `data/orders/` to retrieve order status,
line items, shipping info, and eligibility flags.

Exposed to the agent as a LangChain StructuredTool with inputs:
- order_id: str
- customer_id: str (for ownership verification)
"""
