"""Local, no-API-key RAG: embeddings + in-memory vector store for content grounding (P1 #7).

Imports here stay light — the embedding backend (``fastembed``) is imported lazily inside
``rag.embeddings.get_embeddings`` so the default (RAG-off) path never loads it.
"""
