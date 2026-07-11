"""
Streamlit frontend for the Customer Support Resolution Agent.

Provides a chat-style UI where customers (or evaluators) interact with
the agent. Calls the FastAPI backend at STREAMLIT_API_URL for each turn.

Planned features:

- session sidebar with customer / order context inputs
- message history with agent reasoning trace (optional expand)
- escalation status indicator when human gate is triggered
"""
