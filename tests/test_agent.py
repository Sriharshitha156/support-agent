"""
Tests for LangGraph agent state transitions and node behavior.

Scenarios:

- happy-path order status inquiry
- refund request within policy window
- refund request outside policy window (governance refusal)
- escalation to human gate for high-value refund
"""
