"""
Policy document ingestion pipeline.

Loads raw policy files from `data/policies/` (markdown or JSON) and `data/policies.txt`,
chunks them, embeds via LangChain embeddings, and upserts into the Chroma vector store.

Run once at startup or via a CLI flag to refresh the index.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownTextSplitter

from app.rag.vectorstore import get_chroma_vectorstore

POLICIES_DIR = Path(__file__).resolve().parents[2] / "data" / "policies"
POLICIES_TXT_PATH = Path(__file__).resolve().parents[2] / "data" / "policies.txt"


def load_markdown_documents(directory: Path = POLICIES_DIR) -> list[Document]:
    """Load all markdown files from the policies directory."""
    documents = []
    if not directory.exists():
        return documents
        
    for path in directory.glob("*.md"):
        try:
            content = path.read_text(encoding="utf-8")
            metadata = {
                "source": path.name,
                "category": path.stem.replace("_policy", ""),
            }
            documents.append(Document(page_content=content, metadata=metadata))
        except OSError as exc:
            print(f"Error reading {path}: {exc}")
            
    return documents


def load_txt_document(path: Path = POLICIES_TXT_PATH) -> list[Document]:
    """Load the flat policies.txt file and split into paragraph documents."""
    documents = []
    if not path.exists():
        return documents
        
    try:
        content = path.read_text(encoding="utf-8")
        # Split by double newline to separate individual policies
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for i, p in enumerate(paragraphs):
            metadata = {
                "source": path.name,
                "category": "flat_policies",
                "index": i,
            }
            documents.append(Document(page_content=p, metadata=metadata))
    except OSError as exc:
        print(f"Error reading {path}: {exc}")
        
    return documents


def chunk_documents(documents: list[Document]) -> list[Document]:
    """Chunk documents using MarkdownTextSplitter."""
    splitter = MarkdownTextSplitter(chunk_size=300, chunk_overlap=30)
    return splitter.split_documents(documents)


def ingest_policies() -> int:
    """Load, chunk, and index policies in ChromaDB."""
    print("Starting policy document ingestion...")
    raw_docs = load_markdown_documents()
    txt_docs = load_txt_document()
    
    # Chunk the markdown documents, but keep txt paragraphs intact since they are already small
    chunks = chunk_documents(raw_docs) + txt_docs
    print(f"Loaded {len(raw_docs)} MD docs and {len(txt_docs)} TXT segments; total {len(chunks)} chunks.")
    
    db = get_chroma_vectorstore()
    
    # Reset/clear database collection first if it exists
    try:
        db.delete_collection()
        # Re-initialize to get a clean collection
        db = get_chroma_vectorstore()
    except Exception:
        pass
        
    db.add_documents(chunks)
    print("Ingestion complete. Documents indexed successfully.")
    return len(chunks)


if __name__ == "__main__":
    ingest_policies()
