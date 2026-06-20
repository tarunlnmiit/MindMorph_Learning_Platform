"""In-memory registry of RAG vector stores (P2 #9).

Holds one **per-user** store (the user's ingested material) plus a cached **global** store built from
the shared knowledge base. Stores live in process memory — the MVP scope; swap for a persistent /
pgvector-backed store later without changing callers.

Embeddings are resolved via ``rag.embeddings.get_embeddings`` (imported lazily and indirectly so tests
can monkeypatch it with a fake — no model download).
"""
import logging
from typing import Optional

from rag.store import RagStore, _chunk_text

logger = logging.getLogger(__name__)

_user_stores: dict[str, RagStore] = {}
_global_store: Optional[RagStore] = None
_global_built = False


def _new_store() -> RagStore:
    import rag.embeddings as emb  # indirection so tests can patch get_embeddings

    return RagStore(emb.get_embeddings())


def get_user_store(user_id: str, create: bool = False) -> Optional[RagStore]:
    """Return the user's store. ``create=True`` makes an empty one on first use."""
    if not user_id:
        return None
    store = _user_stores.get(user_id)
    if store is None and create:
        store = _new_store()
        _user_stores[user_id] = store
    return store


def get_global_store() -> Optional[RagStore]:
    """Cached store built from ``config.KNOWLEDGE_DIR`` (shared seed corpus). None if empty/missing."""
    global _global_store, _global_built
    if not _global_built:
        import config

        _global_store = RagStore.from_knowledge_dir(config.KNOWLEDGE_DIR)
        _global_built = True
    return _global_store


def ingest_pdf(user_id: str, data: bytes, filename: str) -> int:
    """Extract a PDF, chunk it, and add it to the user's store. Returns the chunk count."""
    from rag.pdf import extract_text_from_pdf

    text = extract_text_from_pdf(data)
    chunks = _chunk_text(text)
    store = get_user_store(user_id, create=True)
    store.add_texts(chunks, metadatas=[{"source": filename}] * len(chunks))
    logger.info("RAG: ingested %d chunk(s) from %r for user %s", len(chunks), filename, user_id)
    return len(chunks)


def reset() -> None:
    """Clear all stores (test isolation)."""
    global _global_store, _global_built
    _user_stores.clear()
    _global_store = None
    _global_built = False
