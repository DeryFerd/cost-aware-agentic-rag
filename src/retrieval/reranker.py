"""Cross-encoder reranker for retrieval results."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """Reranked result with score."""
    text: str
    score: float
    metadata: dict | None = None
    original_index: int = 0


class CrossEncoderReranker:
    """Rerank retrieval results using a cross-encoder model."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
                logger.info(f"Loaded cross-encoder model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to load cross-encoder: {e}")
                self._model = False  # Mark as failed

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
        metadata_list: list[dict] | None = None,
    ) -> list[RerankResult]:
        """Rerank documents against query using cross-encoder.

        Args:
            query: The search query
            documents: List of document texts to rerank
            top_k: Number of top results to return
            metadata_list: Optional metadata for each document

        Returns:
            List of RerankResult sorted by relevance score
        """
        if not documents:
            return []

        self._load_model()

        # If model failed to load, return documents in original order
        if self._model is False:
            logger.warning("Cross-encoder unavailable, returning original order")
            return [
                RerankResult(
                    text=doc,
                    score=1.0 - (i * 0.01),  # Slight descending score
                    metadata=metadata_list[i] if metadata_list else None,
                    original_index=i,
                )
                for i, doc in enumerate(documents[:top_k])
            ]

        # Create query-document pairs
        pairs = [[query, doc] for doc in documents]

        # Get scores
        scores = self._model.predict(pairs)

        # Create results
        results = []
        for i, (doc, score) in enumerate(zip(documents, scores, strict=False)):
            results.append(RerankResult(
                text=doc,
                score=float(score),
                metadata=metadata_list[i] if metadata_list else None,
                original_index=i,
            ))

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_k]

    def rerank_with_texts(
        self,
        query: str,
        texts: list[str],
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """Simple reranking returning (text, score) tuples.

        Args:
            query: The search query
            texts: List of document texts
            top_k: Number of results to return

        Returns:
            List of (text, score) tuples sorted by relevance
        """
        results = self.rerank(query, texts, top_k)
        return [(r.text, r.score) for r in results]
