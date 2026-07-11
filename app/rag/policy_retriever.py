"""Policy retrieval using LangChain text splitting and an in-memory vector store."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_community.embeddings import FakeEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import CharacterTextSplitter

POLICIES_PATH = Path(__file__).resolve().parents[2] / "data" / "policies.txt"


@lru_cache(maxsize=1)
def _load_vectorstore() -> InMemoryVectorStore:
    """Load policies from disk, split, embed, and cache the vector store."""
    raw_text = POLICIES_PATH.read_text(encoding="utf-8")
    splitter = CharacterTextSplitter(separator="\n\n", chunk_size=200, chunk_overlap=20)
    chunks = splitter.split_text(raw_text)
    embeddings = FakeEmbeddings(size=128)
    return InMemoryVectorStore.from_texts(chunks, embedding=embeddings)


def retrieve_policy(query: str, *, k: int = 2) -> list[dict]:
    """
    Return the most relevant policy snippets for a user query.

    Each result includes the snippet text and similarity score.
    """
    if not query.strip():
        return []

    store = _load_vectorstore()
    results = store.similarity_search_with_score(query, k=k)
    return [
        {
            "snippet": document.page_content,
            "score": float(score),
            "metadata": document.metadata,
        }
        for document, score in results
    ]


def retrieve_policy_text(query: str, *, k: int = 2) -> str:
    """Return policy snippets joined as a single string for LLM / agent context."""
    snippets = retrieve_policy(query, k=k)
    if not snippets:
        return "No matching policy found."
    return "\n".join(f"- {item['snippet']}" for item in snippets)
