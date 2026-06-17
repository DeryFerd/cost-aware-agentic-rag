"""Reciprocal Rank Fusion (RRF) for combining multiple retrieval lists."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FusedResult:
    """Fused result from multiple retrieval sources."""
    text: str
    rrf_score: float
    metadata: dict | None = None
    source_scores: dict | None = None


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, dict | None]]],
    k: int = 60,
    top_k: int = 20,
) -> list[FusedResult]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion.

    RRF score = Σ 1/(k + rank_i) for each list where document appears.

    Args:
        ranked_lists: List of ranked results, each is [(text, metadata), ...]
        k: RRF constant (default 60, standard in literature)
        top_k: Number of top results to return

    Returns:
        List of FusedResult sorted by RRF score descending
    """
    # Dictionary to accumulate RRF scores
    doc_scores: dict[str, float] = {}
    doc_metadata: dict[str, dict | None] = {}
    doc_source_scores: dict[str, dict] = {}

    for list_idx, ranked_list in enumerate(ranked_lists):
        for rank, (text, metadata) in enumerate(ranked_list):
            # Normalize text for deduplication
            key = text.strip()[:500]  # Use first 500 chars as key

            if key not in doc_scores:
                doc_scores[key] = 0.0
                doc_metadata[key] = metadata
                doc_source_scores[key] = {}

            # RRF formula: 1 / (k + rank)
            rrf_contribution = 1.0 / (k + rank + 1)  # rank is 0-indexed
            doc_scores[key] += rrf_contribution
            doc_source_scores[key][f"list_{list_idx}"] = rrf_contribution

    # Sort by total RRF score
    sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for text_key, score in sorted_docs[:top_k]:
        results.append(FusedResult(
            text=text_key,
            rrf_score=score,
            metadata=doc_metadata.get(text_key),
            source_scores=doc_source_scores.get(text_key),
        ))

    return results


def weighted_score_fusion(
    ranked_lists: list[list[tuple[str, float, dict | None]]],
    weights: list[float] | None = None,
    top_k: int = 20,
) -> list[FusedResult]:
    """Combine ranked lists using weighted score fusion (original method).

    This is the existing fusion method, kept for backward compatibility.

    Args:
        ranked_lists: List of ranked results, each is [(text, score, metadata), ...]
        weights: Weight for each list (must sum to 1.0)
        top_k: Number of top results to return

    Returns:
        List of FusedResult sorted by weighted score descending
    """
    if weights is None:
        weights = [1.0 / len(ranked_lists)] * len(ranked_lists)

    # Normalize weights
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]

    # Collect all unique documents
    doc_scores: dict[str, float] = {}
    doc_metadata: dict[str, dict | None] = {}
    doc_source_scores: dict[str, dict] = {}

    for list_idx, ranked_list in enumerate(ranked_lists):
        # Find max score for normalization
        max_score = max((score for _, score, _ in ranked_list), default=1.0)
        if max_score == 0:
            max_score = 1.0

        for text, score, metadata in ranked_list:
            key = text.strip()[:500]
            normalized_score = score / max_score

            if key not in doc_scores:
                doc_scores[key] = 0.0
                doc_metadata[key] = metadata
                doc_source_scores[key] = {}

            doc_scores[key] += normalized_score * weights[list_idx]
            doc_source_scores[key][f"list_{list_idx}"] = normalized_score

    # Sort by weighted score
    sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for text_key, score in sorted_docs[:top_k]:
        results.append(FusedResult(
            text=text_key,
            rrf_score=score,
            metadata=doc_metadata.get(text_key),
            source_scores=doc_source_scores.get(text_key),
        ))

    return results
