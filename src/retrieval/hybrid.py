"""Hybrid retrieval combining vector, BM25, and ColPali scores."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import settings
from src.retrieval.vector_store import VectorStore
from src.retrieval.bm25_index import BM25Index


@dataclass
class RetrievalResult:
    text: str
    score: float
    vector_score: float = 0.0
    bm25_score: float = 0.0
    metadata: dict | None = None


class HybridRetriever:
    """Multi-index retrieval with score fusion."""

    def __init__(self) -> None:
        self.vector_store = VectorStore()
        self.bm25_index = BM25Index()
        self._weights = {"vector": 0.6, "bm25": 0.4}

    def build_index(self, chunks: list[dict], ticker: str) -> None:
        """Build both vector and BM25 indices from chunks."""
        self.vector_store.add_documents(chunks, ticker)
        self.bm25_index.add_documents(chunks)
        self.bm25_index.save()

    def retrieve(
        self,
        query: str,
        top_k: int = settings.top_k,
        weights: dict[str, float] | None = None,
    ) -> list[RetrievalResult]:
        """Hybrid retrieval with normalized score fusion."""
        weights = weights or self._weights

        # Vector search
        vector_results = self.vector_store.search(query, top_k=top_k * 2)
        vector_scores = {r["text"]: r["score"] for r in vector_results}

        # BM25 search
        bm25_results = self.bm25_index.search(query, top_k=top_k * 2)
        bm25_scores = {r["text"]: r["score"] for r in bm25_results}

        # Normalize scores
        all_texts = set(vector_scores.keys()) | set(bm25_scores.keys())
        if not all_texts:
            return []

        max_vector = max(vector_scores.values()) if vector_scores else 1.0
        max_bm25 = max(bm25_scores.values()) if bm25_scores else 1.0

        # Fuse scores
        fused: list[RetrievalResult] = []
        for text in all_texts:
            v_norm = vector_scores.get(text, 0) / max_vector if max_vector else 0
            b_norm = bm25_scores.get(text, 0) / max_bm25 if max_bm25 else 0

            fused_score = weights["vector"] * v_norm + weights["bm25"] * b_norm

            # Find metadata from either result set
            meta = None
            for r in vector_results + bm25_results:
                if r["text"] == text:
                    meta = r.get("metadata")
                    break

            fused.append(
                RetrievalResult(
                    text=text,
                    score=fused_score,
                    vector_score=v_norm,
                    bm25_score=b_norm,
                    metadata=meta,
                )
            )

        # Sort by fused score and return top_k
        fused.sort(key=lambda x: x.score, reverse=True)
        return fused[:top_k]

    def load_indices(self) -> bool:
        """Load existing indices from disk."""
        return self.bm25_index.load()

    def stats(self) -> dict:
        return {
            "vector_count": self.vector_store.count(),
            "bm25_count": self.bm25_index.count(),
        }
