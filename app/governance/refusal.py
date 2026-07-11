"""
Refusal and policy compliance logic.

Evaluates agent outputs and tool requests before they reach the customer.
Blocks or modifies responses that:

- violate refund limits or eligibility rules
- disclose PII of other customers
- promise actions outside agent authority
- bypass required human approval for high-risk operations

Returns allow / refuse / escalate decisions consumed by graph nodes.
"""
