"""Local embeddings for RAG — FastEmbed (ONNX, no torch, no API key) wrapped as a LangChain
``Embeddings`` so it drops straight into ``InMemoryVectorStore``.

``fastembed`` is imported lazily inside ``get_embeddings`` so importing this module (or the RAG-off
content path) never pulls the ONNX runtime or triggers a model download.
"""
import logging
from typing import Any, List

from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

# FastEmbed's small, fast default. ~130MB ONNX, downloaded once on first use.
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class FastEmbedEmbeddings(Embeddings):
    """LangChain ``Embeddings`` backed by ``fastembed.TextEmbedding``."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        from fastembed import TextEmbedding  # lazy: only when RAG is actually used

        logger.info("RAG: loading FastEmbed model %s", model_name)
        self._model: Any = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [v.tolist() for v in self._model.embed(list(texts))]

    def embed_query(self, text: str) -> List[float]:
        return next(iter(self._model.embed([text]))).tolist()


def get_embeddings(model_name: str = DEFAULT_MODEL) -> Embeddings:
    """Return the default local embeddings backend. Injectable; tests pass a fake instead."""
    return FastEmbedEmbeddings(model_name=model_name)
