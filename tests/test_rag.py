"""Tests for policy retrieval."""

from app.rag.policy_retriever import retrieve_policy, retrieve_policy_text


def test_retrieve_policy_refund():
    results = retrieve_policy("refund over ten dollars manager approval")
    assert results
    assert any("manager" in item["snippet"].lower() for item in results)


def test_retrieve_policy_legal_escalation():
    results = retrieve_policy("customer mentioned lawyer sue legal complaint escalate immediately")
    assert results
    joined = " ".join(item["snippet"].lower() for item in results)
    assert "legal" in joined or "escalat" in joined or "lawyer" in joined


def test_retrieve_policy_text_joins_snippets():
    text = retrieve_policy_text("late order refund under 10 dollars")
    assert "Policy" in text
    assert "-" in text
