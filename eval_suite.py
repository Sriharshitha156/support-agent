"""
Evaluation suite for the Customer Support Resolution Agent.

Runs scripted scenarios against the compiled LangGraph agent and reports:

- intent classification accuracy
- correct tool selection rate
- policy citation quality (RAG hit rate)
- governance refusal correctness
- end-to-end resolution success

Usage:
    python eval_suite.py
    python eval_suite.py --scenarios tests/scenarios/
"""
