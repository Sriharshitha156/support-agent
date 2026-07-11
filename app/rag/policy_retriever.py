"""Policy retrieval using ChromaDB vector store or in-memory fallback."""

from __future__ import annotations

from app.rag.vectorstore import retrieve_policies_from_chroma


def retrieve_policy(query: str, *, k: int = 2) -> list[dict]:
    """
    Return the most relevant policy snippets for a user query.

    Each result includes the snippet text, similarity score, and metadata.
    """
    if not query.strip():
        return []

    # Retrieve from the persistent ChromaDB (configured with fallback SimpleTFIDFEmbeddings)
    results = retrieve_policies_from_chroma(query, k=k)
    
    # Self-healing ingestion check: if Chroma contains no documents, run ingestion first
    if not results:
        try:
            from app.rag.ingestion import ingest_policies
            count = ingest_policies()
            if count > 0:
                results = retrieve_policies_from_chroma(query, k=k)
        except Exception as exc:
            print(f"Self-healing policy ingestion failed: {exc}")

    # Format output format to match tests/agent expectations
    formatted_results = []
    for item in results:
        formatted_results.append({
            "snippet": item["snippet"],
            "score": item["score"],
            "metadata": item["metadata"],
        })
    return formatted_results


def retrieve_policy_text(query: str, *, k: int = 2) -> str:
    """Return policy snippets joined as a single string for LLM / agent context."""
    snippets = retrieve_policy(query, k=k)
    if not snippets:
        return "No matching policy found."
    return "\n".join(f"- {item['snippet']}" for item in snippets)
