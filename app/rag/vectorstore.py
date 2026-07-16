"""
ChromaDB vector store setup and retrieval interface.

Responsibilities:
- Initialize / persist Chroma collection for support policies.
- Embed and store policy chunks from `data/policies/`.
- Expose a retriever function used by the `retrieve_policy` graph node.
- Support similarity search with optional metadata filters (category, date).
"""

from __future__ import annotations

import os
import zlib
from pathlib import Path
from typing import Any, List, Dict

from dotenv import load_dotenv
load_dotenv()

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
except ImportError:
    GoogleGenerativeAIEmbeddings = None  # type: ignore[misc,assignment]

# Custom stateless Feature Hashing Embeddings for testing/offline usage
class HashingEmbeddings(Embeddings):
    def __init__(self, dimension: int = 128):
        self.dimension = dimension

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        words = text.lower().split()
        for word in words:
            cleaned = "".join(char for char in word if char.isalnum())
            if cleaned:
                # Adler32 provides a fast, stable, cross-platform hash
                h = zlib.adler32(cleaned.encode("utf-8"))
                index = h % self.dimension
                vector[index] += 1.0
        
        # L2 Normalize the vector
        magnitude = sum(x * x for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
            
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)


def get_embeddings_model() -> Embeddings:
    """Return best available embeddings model, falling back through providers to local HashingEmbeddings."""
    model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Priority 1: Google Gemini (free tier: 1500 req/day)
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key and GoogleGenerativeAIEmbeddings is not None:
        try:
            model = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=google_key,
            )
            model.embed_query("probe")
            return model
        except Exception as exc:
            print(f"Embeddings API (Google Gemini) unavailable: {exc}")

    # Priority 2: Explicit EMBEDDING_API_BASE (e.g. OpenRouter, custom provider)
    embedding_base = os.getenv("EMBEDDING_API_BASE")
    embedding_key = os.getenv("OPENAI_API_KEY")

    if embedding_base and embedding_key and not embedding_key.startswith("sk-your-openai-api-key"):
        try:
            model = OpenAIEmbeddings(
                openai_api_key=embedding_key,
                model=model_name,
                openai_api_base=embedding_base,
            )
            model.embed_query("probe")
            return model
        except Exception as exc:
            print(f"Embeddings API ({embedding_base}) unavailable: {exc}")

    # Priority 3: GITHUB_TOKEN → GitHub Models endpoint
    g_token = os.getenv("GITHUB_TOKEN")
    if g_token and not g_token.startswith("gh-your-github-token"):
        base_url = os.getenv("OPENAI_API_BASE") or "https://models.inference.ai.azure.com"
        try:
            model = OpenAIEmbeddings(
                openai_api_key=g_token,
                model=model_name,
                openai_api_base=base_url,
            )
            model.embed_query("probe")
            return model
        except Exception as exc:
            print(f"Embeddings API (GitHub Models) unavailable: {exc}")

    # Priority 4: OPENAI_API_KEY → default OpenAI endpoint
    o_key = os.getenv("OPENAI_API_KEY")
    if o_key and not o_key.startswith("sk-your-openai-api-key"):
        base_url = os.getenv("OPENAI_API_BASE")
        try:
            model = OpenAIEmbeddings(
                openai_api_key=o_key,
                model=model_name,
                openai_api_base=base_url,
            )
            model.embed_query("probe")
            return model
        except Exception as exc:
            print(f"Embeddings API unavailable: {exc}")

    print("No valid API key found for embeddings — using local HashingEmbeddings fallback.")
    return HashingEmbeddings()


def get_vectorstore_dir() -> str:
    """Get Chroma persistent directory from env or defaults."""
    return os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")


def get_chroma_vectorstore() -> Chroma:
    """Initialize and return the persistent Chroma vector store."""
    persist_dir = get_vectorstore_dir()
    embeddings = get_embeddings_model()
    
    # Ensure parent dir exists
    Path(persist_dir).parent.mkdir(parents=True, exist_ok=True)
    
    return Chroma(
        collection_name="support_policies",
        embedding_function=embeddings,
        persist_directory=persist_dir
    )


def retrieve_policies_from_chroma(
    query: str, 
    k: int = 2, 
    metadata_filter: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Search the ChromaDB vector store for relevant policy chunks.
    
    Returns structured results containing snippet, score, and metadata.
    """
    if not query.strip():
        return []
        
    db = get_chroma_vectorstore()
    
    results = db.similarity_search_with_score(query, k=k, filter=metadata_filter)
    
    return [
        {
            "snippet": doc.page_content,
            "score": float(score),
            "metadata": doc.metadata,
        }
        for doc, score in results
    ]
