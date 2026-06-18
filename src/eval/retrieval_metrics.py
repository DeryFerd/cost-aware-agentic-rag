"""Retrieval evaluation metrics for RAG systems.

Implements:
- NDCG@K (Normalized Discounted Cumulative Gain)
- MRR (Mean Reciprocal Rank)
- Recall@K
- Precision@K
- Hit Rate
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result of retrieval evaluation."""
    ndcg_at_10: float = 0.0
    mrr: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    hit_rate: float = 0.0
    total_queries: int = 0
    per_query: list[dict] = field(default_factory=list)


def _dcg(relevances: list[int], k: int) -> float:
    """Compute DCG@k.

    Args:
        relevances: List of binary relevance scores (1 = relevant, 0 = not).
        k: Number of positions to consider.

    Returns:
        DCG score.
    """
    score = 0.0
    for i, rel in enumerate(relevances[:k]):
        score += rel / math.log2(i + 2)  # i+2 because log2(1) = 0
    return score


def _ndcg_at_k(relevances: list[int], k: int) -> float:
    """Compute NDCG@k.

    Args:
        relevances: List of binary relevance scores.
        k: Number of positions to consider.

    Returns:
        NDCG score between 0 and 1.
    """
    dcg = _dcg(relevances, k)

    # Ideal DCG: all relevant documents at the top
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = _dcg(ideal_relevances, k)

    if idcg == 0:
        return 0.0
    return dcg / idcg


def _mrr(ranked_relevances: list[int]) -> float:
    """Compute Mean Reciprocal Rank.

    Args:
        ranked_relevances: List of binary relevance scores in ranked order.

    Returns:
        Reciprocal rank of the first relevant document.
    """
    for i, rel in enumerate(ranked_relevances):
        if rel > 0:
            return 1.0 / (i + 1)
    return 0.0


def _recall_at_k(retrieved: list[int], relevant_set: set[int], k: int) -> float:
    """Compute Recall@k.

    Args:
        retrieved: List of document indices in ranked order.
        relevant_set: Set of relevant document indices.
        k: Number of top documents to consider.

    Returns:
        Recall score between 0 and 1.
    """
    if not relevant_set:
        return 0.0

    retrieved_at_k = set(retrieved[:k])
    hits = len(retrieved_at_k & relevant_set)
    return hits / len(relevant_set)


def _precision_at_k(retrieved: list[int], relevant_set: set[int], k: int) -> float:
    """Compute Precision@k.

    Args:
        retrieved: List of document indices in ranked order.
        relevant_set: Set of relevant document indices.
        k: Number of top documents to consider.

    Returns:
        Precision score between 0 and 1.
    """
    if k == 0:
        return 0.0

    retrieved_at_k = retrieved[:k]
    hits = sum(1 for idx in retrieved_at_k if idx in relevant_set)
    return hits / k


def evaluate_retrieval(
    queries: list[dict],
    retriever_fn,
    k_values: list[int] | None = None,
) -> RetrievalResult:
    """Evaluate retrieval quality across multiple queries.

    Args:
        queries: List of dicts with 'query' and 'relevant_ids' keys.
                 'relevant_ids' should be a set of document IDs that are relevant.
        retriever_fn: Function that takes a query string and returns a list of
                      document IDs in ranked order.
        k_values: List of k values for Recall@k and Precision@k.
                  Defaults to [5, 10].

    Returns:
        RetrievalResult with aggregated metrics.
    """
    if k_values is None:
        k_values = [5, 10]

    ndcg_scores = []
    mrr_scores = []
    recall_scores = {k: [] for k in k_values}
    precision_scores = {k: [] for k in k_values}
    hit_count = 0
    per_query = []

    for q in queries:
        query = q["query"]
        relevant_set = set(q.get("relevant_ids", []))

        # Get retrieved document IDs
        retrieved_ids = retriever_fn(query)
        retrieved_indices = list(range(len(retrieved_ids)))

        # Create relevance array
        relevances = [1 if doc_id in relevant_set else 0 for doc_id in retrieved_ids]

        # NDCG@10
        ndcg = _ndcg_at_k(relevances, 10)
        ndcg_scores.append(ndcg)

        # MRR
        mrr = _mrr(relevances)
        mrr_scores.append(mrr)

        # Recall@k and Precision@k
        for k in k_values:
            recall = _recall_at_k(retrieved_indices, relevant_set, k)
            recall_scores[k].append(recall)

            precision = _precision_at_k(retrieved_indices, relevant_set, k)
            precision_scores[k].append(precision)

        # Hit rate
        if any(rel > 0 for rel in relevances[:10]):
            hit_count += 1

        per_query.append({
            "query": query,
            "ndcg_at_10": ndcg,
            "mrr": mrr,
            "recall_at_5": recall_scores[5][-1],
            "recall_at_10": recall_scores[10][-1] if len(recall_scores[10]) > 0 else 0,
            "relevant_count": len(relevant_set),
            "retrieved_count": len(retrieved_ids),
        })

    total = len(queries) if queries else 1

    result = RetrievalResult(
        ndcg_at_10=sum(ndcg_scores) / total if ndcg_scores else 0.0,
        mrr=sum(mrr_scores) / total if mrr_scores else 0.0,
        recall_at_5=sum(recall_scores[5]) / total if recall_scores[5] else 0.0,
        recall_at_10=sum(recall_scores[10]) / total if recall_scores[10] else 0.0,
        precision_at_5=sum(precision_scores[5]) / total if precision_scores[5] else 0.0,
        precision_at_10=sum(precision_scores[10]) / total if precision_scores[10] else 0.0,
        hit_rate=hit_count / total,
        total_queries=len(queries),
        per_query=per_query,
    )

    logger.info(
        f"Retrieval eval: NDCG@10={result.ndcg_at_10:.3f}, "
        f"MRR={result.mrr:.3f}, Recall@5={result.recall_at_5:.3f}, "
        f"Hit Rate={result.hit_rate:.3f}"
    )

    return result


def evaluate_with_golden_set(
    golden_set: list[dict],
    retriever_fn,
) -> RetrievalResult:
    """Evaluate retrieval using the golden set.

    Args:
        golden_set: List of dicts with 'question', 'company', 'answer' keys.
        retriever_fn: Function that takes a query string and returns a list of
                      document IDs in ranked order.

    Returns:
        RetrievalResult with aggregated metrics.
    """
    queries = []
    for item in golden_set:
        queries.append({
            "query": item["question"],
            "relevant_ids": {item.get("company", "")},  # Use company as relevant ID
        })

    return evaluate_retrieval(queries, retriever_fn)
