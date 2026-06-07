"""Hybrid retrieval combining vector, BM25, and re-ranking."""

from __future__ import annotations

import re
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
    rerank_score: float = 0.0
    metadata: dict | None = None


def _extract_ticker_from_query(query: str) -> str | None:
    """Extract company ticker from query."""
    tickers = {
        "MSFT": ["microsoft", "msft"],
        "AMZN": ["amazon", "amzn"],
        "META": ["meta", "facebook", "meta platforms"],
        "GOOG": ["google", "alphabet", "goog"],
        "TSLA": ["tesla", "tsla"],
    }

    query_lower = query.lower()
    for ticker, keywords in tickers.items():
        for kw in keywords:
            if kw in query_lower:
                return ticker
    return None


def _extract_year_from_query(query: str) -> str | None:
    """Extract year from query."""
    match = re.search(r"\b(20\d{2})\b", query)
    return match.group(1) if match else None


def _compute_keyword_overlap(query: str, text: str) -> float:
    """Compute keyword overlap between query and text."""
    query_words = set(query.lower().split())
    text_words = set(text.lower().split())

    # Remove common stop words
    stop_words = {"the", "a", "an", "in", "on", "at", "for", "to", "of", "and", "or", "was", "were", "is", "are"}
    query_words -= stop_words
    text_words -= stop_words

    if not query_words:
        return 0.0

    overlap = query_words & text_words
    return len(overlap) / len(query_words)


class HybridRetriever:
    """Multi-index retrieval with score fusion and re-ranking."""

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
        use_filters: bool = True,
    ) -> list[RetrievalResult]:
        """Hybrid retrieval with filtering and re-ranking."""
        weights = weights or self._weights

        # Extract filters from query
        ticker_filter = _extract_ticker_from_query(query) if use_filters else None
        year_filter = _extract_year_from_query(query) if use_filters else None

        # Vector search with filters
        vector_results = self.vector_store.search(
            query,
            top_k=top_k * 3,
            ticker_filter=ticker_filter,
            year_filter=year_filter,
        )
        vector_scores = {r["text"]: r["score"] for r in vector_results}

        # BM25 search
        bm25_results = self.bm25_index.search(query, top_k=top_k * 3)
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

        # Re-rank based on keyword overlap
        for result in fused:
            result.rerank_score = _compute_keyword_overlap(query, result.text)
            # Boost score if metadata matches query
            if meta:
                if ticker_filter and meta.get("ticker") == ticker_filter:
                    result.rerank_score += 0.2
                if year_filter and meta.get("year") == year_filter:
                    result.rerank_score += 0.1

        # Final score: 60% fused + 40% rerank
        for result in fused:
            result.score = 0.6 * result.score + 0.4 * result.rerank_score

        # Sort by final score and return top_k
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
