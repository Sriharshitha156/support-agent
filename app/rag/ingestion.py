"""
Policy document ingestion pipeline.

Loads raw policy files from `data/policies/` (markdown or JSON),
chunks them with a text splitter, embeds via LangChain embeddings,
and upserts into the Chroma vector store.

Run once at startup or via a CLI flag to refresh the index.
"""
