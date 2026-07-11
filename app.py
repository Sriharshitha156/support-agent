"""
FastAPI backend for the Customer Support Resolution Agent.

Exposes REST endpoints:

- POST /chat          — send a customer message, receive agent response
- GET  /health        — liveness check
- POST /ingest        — trigger policy document ingestion (admin)
- GET  /audit/{session_id} — retrieve audit trail for a session

Initializes the compiled LangGraph agent on startup and wires CORS for
the Streamlit frontend. Configuration loaded from environment / .env.
"""
