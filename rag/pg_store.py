"""pgvector-backed per-user RAG store (P2 #9 persistence).

Same surface as the in-memory ``RagStore`` (``add_texts`` / ``retrieve`` / ``is_empty``) but durable:
each chunk + its FastEmbed vector is a row in ``rag_chunks`` scoped to ``user_id``; retrieval is a
cosine-distance query filtered to that user. SQLAlchemy/embeddings are imported lazily so importing
this module needs no DB and never loads fastembed.
"""
import logging
from typing import List, Optional

from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

DEFAULT_K = 4


class PgRagStore:
    """A per-user, Postgres-persisted vector store handle (stateless — the data lives in the DB)."""

    def __init__(self, user_id: str, embeddings: Optional[Embeddings] = None):
        self.user_id = user_id
        self._embeddings = embeddings

    def _emb(self) -> Embeddings:
        if self._embeddings is None:
            import rag.embeddings as emb

            self._embeddings = emb.get_embeddings()
        return self._embeddings

    def add_texts(self, texts: List[str], metadatas: Optional[List[dict]] = None) -> None:
        texts = [t for t in texts if t and t.strip()]
        if not texts:
            return
        from persistence.db import get_sessionmaker
        from persistence.models import RagChunkRow

        vectors = self._emb().embed_documents(texts)
        metadatas = metadatas or [{} for _ in texts]
        rows = [
            RagChunkRow(
                user_id=self.user_id,
                source=(m or {}).get("source", "upload"),
                content=t,
                embedding=v,
            )
            for t, v, m in zip(texts, vectors, metadatas)
        ]
        with get_sessionmaker()() as session:
            session.add_all(rows)
            session.commit()
        logger.info("RAG(pg): stored %d chunk(s) for user %s", len(rows), self.user_id)

    @property
    def is_empty(self) -> bool:
        from sqlalchemy import func, select

        from persistence.db import get_sessionmaker
        from persistence.models import RagChunkRow

        with get_sessionmaker()() as session:
            n = session.execute(
                select(func.count())
                .select_from(RagChunkRow)
                .where(RagChunkRow.user_id == self.user_id)
            ).scalar_one()
        return n == 0

    def retrieve(self, query: str, k: int = DEFAULT_K) -> Optional[str]:
        if not query or not query.strip():
            return None
        from sqlalchemy import select

        from persistence.db import get_sessionmaker
        from persistence.models import RagChunkRow

        qvec = self._emb().embed_query(query)
        try:
            with get_sessionmaker()() as session:
                rows = session.execute(
                    select(RagChunkRow.content, RagChunkRow.source)
                    .where(RagChunkRow.user_id == self.user_id)
                    .order_by(RagChunkRow.embedding.cosine_distance(qvec))
                    .limit(k)
                ).all()
        except Exception:
            logger.exception("RAG(pg): retrieval failed for user %s", self.user_id)
            return None
        if not rows:
            return None
        return "\n".join(f"- {content}\n  Source: {source}" for content, source in rows)
