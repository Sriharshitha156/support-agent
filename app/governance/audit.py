"""
Structured audit logging for agent actions.

Records every significant event with timestamp, session ID, actor, action,
and outcome. Events include:

- tool invocations (order lookup, refund attempt)
- RAG retrievals and sources cited
- governance refusals and escalations
- final responses sent to the customer

Writes to `data/audit.log` (path configurable via AUDIT_LOG_PATH).
"""
