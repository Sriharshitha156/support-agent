"""
Mock refund processing tool.

Simulates initiating a refund against an order. Validates:

- order exists and belongs to customer
- order is within refund window per policy
- refund amount does not exceed governance limits

Returns a mock confirmation ID or a structured rejection reason.
"""
