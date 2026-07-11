"""
Human-in-the-loop gate simulation.

When the agent cannot resolve autonomously (high-value refund, policy
exception, angry escalation), this tool pauses the graph and records a
handoff request for a human agent.

In production this would integrate with a ticketing / queue system; here
it writes to the audit log and returns a simulated ticket ID.
"""
