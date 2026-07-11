"""
ChromaDB vector store setup and retrieval interface.

Responsibilities:

- initialize / persist Chroma collection for support policies
- embed and store policy chunks from `data/policies/`
- expose a retriever function used by the `retrieve_policy` graph node
- support similarity search with optional metadata filters (category, date)
"""
