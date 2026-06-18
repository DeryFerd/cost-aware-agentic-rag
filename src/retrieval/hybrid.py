"""Hybrid retrieval combining vector, BM25, RRF fusion, and cross-encoder reranking."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from src.config import settings
from src.observability.tracing import tracer
from src.retrieval.bm25_index import BM25Index
from src.retrieval.fusion import reciprocal_rank_fusion
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.vector_store import VectorStore

try:
    from opentelemetry import trace as otel_trace
except ImportError:
    otel_trace = None


@dataclass
class RetrievalResult:
    text: str
    score: float
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rerank_score: float = 0.0
    rrf_score: float = 0.0
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


class HybridRetriever:
    """Multi-index retrieval with RRF fusion and cross-encoder reranking."""

    def __init__(self, use_cross_encoder: bool = True) -> None:
        self.vector_store = VectorStore()
        self.bm25_index = BM25Index()
        self.use_cross_encoder = use_cross_encoder
        self._reranker = CrossEncoderReranker() if use_cross_encoder else None

    def build_index(self, chunks: list[dict], ticker: str) -> None:
        """Build both vector and BM25 indices from chunks."""
        self.vector_store.add_documents(chunks, ticker)
        self.bm25_index.add_documents(chunks)
        self.bm25_index.save()

    def retrieve(
        self,
        query: str,
        top_k: int = settings.top_k,
        use_filters: bool = True,
        use_rrf: bool = True,
    ) -> list[RetrievalResult]:
        """Hybrid retrieval with RRF fusion and cross-encoder reranking."""
        span_ctx = None
        if tracer is not None and otel_trace is not None:
            span_ctx = tracer.start_as_current_span("hybrid_retrieve")
            span = span_ctx.__enter__()
            span.set_attribute("query", query[:200])
            span.set_attribute("top_k", top_k)
            span.set_attribute("use_filters", use_filters)
            span.set_attribute("use_rrf", use_rrf)
            t0 = time.perf_counter()

        try:
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

            # BM25 search
            bm25_results = self.bm25_index.search(query, top_k=top_k * 3)

            # Convert to ranked lists for RRF
            vector_ranked = [(r["text"], r.get("metadata")) for r in vector_results]
            bm25_ranked = [(r["text"], r.get("metadata")) for r in bm25_results]

            # Fuse using RRF or weighted sum
            if use_rrf and (vector_ranked or bm25_ranked):
                fused_results = reciprocal_rank_fusion(
                    ranked_lists=[vector_ranked, bm25_ranked],
                    k=60,
                    top_k=top_k * 3,
                )
                fused = [
                    RetrievalResult(
                        text=r.text,
                        score=r.rrf_score,
                        rrf_score=r.rrf_score,
                        metadata=r.metadata,
                    )
                    for r in fused_results
                ]
            else:
                # Fallback: simple weighted fusion
                fused = self._weighted_fusion(vector_results, bm25_results, top_k * 3)

            # Cross-encoder reranking
            if self.use_cross_encoder and self._reranker and fused:
                texts = [r.text for r in fused]
                reranked = self._reranker.rerank(query, texts, top_k=top_k)

                # Update scores with cross-encoder scores
                text_to_idx = {r.text: i for i, r in enumerate(fused)}
                results = []
                for rr in reranked:
                    idx = text_to_idx.get(rr.text)
                    if idx is not None:
                        orig = fused[idx]
                        results.append(RetrievalResult(
                            text=rr.text,
                            score=rr.score,
                            vector_score=orig.vector_score,
                            bm25_score=orig.bm25_score,
                            rerank_score=rr.score,
                            rrf_score=orig.rrf_score,
                            metadata=orig.metadata,
                        ))
                final = results[:top_k]
            else:
                # No reranking, just sort by fused score
                fused.sort(key=lambda x: x.score, reverse=True)
                final = fused[:top_k]

            if span_ctx is not None:
                span.set_attribute("results_count", len(final))
                span.set_attribute("vector_candidates", len(vector_results))
                span.set_attribute("bm25_candidates", len(bm25_results))
                span.set_attribute("reranked", self.use_cross_encoder and bool(fused))

            return final

        finally:
            if span_ctx is not None:
                latency_ms = (time.perf_counter() - t0) * 1000
                span.set_attribute("duration_ms", round(latency_ms, 2))
                span_ctx.__exit__(None, None, None)

    def _weighted_fusion(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Fallback weighted score fusion."""
        weights = {"vector": 0.6, "bm25": 0.4}

        vector_scores = {r["text"]: r["score"] for r in vector_results}
        bm25_scores = {r["text"]: r["score"] for r in bm25_results}

        all_texts = set(vector_scores.keys()) | set(bm25_scores.keys())
        if not all_texts:
            return []

        max_vector = max(vector_scores.values()) if vector_scores else 1.0
        max_bm25 = max(bm25_scores.values()) if bm25_scores else 1.0

        fused = []
        for text in all_texts:
            v_norm = vector_scores.get(text, 0) / max_vector if max_vector else 0
            b_norm = bm25_scores.get(text, 0) / max_bm25 if max_bm25 else 0
            fused_score = weights["vector"] * v_norm + weights["bm25"] * b_norm

            meta = None
            for r in vector_results + bm25_results:
                if r["text"] == text:
                    meta = r.get("metadata")
                    break

            fused.append(RetrievalResult(
                text=text,
                score=fused_score,
                vector_score=v_norm,
                bm25_score=b_norm,
                metadata=meta,
            ))

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
