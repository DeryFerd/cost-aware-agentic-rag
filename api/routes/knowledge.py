"""Knowledge graph and evaluation endpoints."""

from __future__ import annotations

import contextlib
import logging

from fastapi import APIRouter

from src.config import settings
from src.eval.pipeline import CIGating, EvalPipeline
from src.knowledge.graph import FinancialKnowledgeGraph

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/knowledge/stats")
def knowledge_graph_stats():
    """Get knowledge graph statistics."""
    kg = FinancialKnowledgeGraph(
        storage_path=settings.data_dir / "knowledge_graph.json"
    )
    with contextlib.suppress(Exception):
        kg.load()
    return kg.get_stats()


@router.get("/knowledge/entity/{entity}")
def knowledge_entity(entity: str):
    """Query knowledge graph for an entity."""
    kg = FinancialKnowledgeGraph(
        storage_path=settings.data_dir / "knowledge_graph.json"
    )
    with contextlib.suppress(Exception):
        kg.load()
    return kg.query_entity(entity)


@router.post("/knowledge/extract")
def knowledge_extract(text: str):
    """Extract entities and triples from text."""
    kg = FinancialKnowledgeGraph()
    return kg.build_from_text(text)


@router.post("/eval/run")
def eval_run(query: str, answer: str, ground_truth: str | None = None):
    """Run evaluation on a query-answer pair."""
    from src.retrieval.hybrid import HybridRetriever

    retriever = HybridRetriever()
    docs = retriever.retrieve(query, top_k=5)
    doc_texts = [d.text for d in docs]

    pipeline = EvalPipeline(storage_path=settings.data_dir / "eval_pipeline")
    report = pipeline.evaluate(
        query=query,
        retrieved_docs=doc_texts,
        answer=answer,
        ground_truth=ground_truth,
    )

    gating = CIGating()
    gate_result = gating.check(report)

    return {
        "overall_score": report.overall_score,
        "metrics": [{"metric": r.metric_name, "value": r.value} for r in report.results],
        "ci_gates": gate_result,
    }


@router.get("/eval/history")
def eval_history(limit: int = 20):
    """Get evaluation history."""
    from src.eval.pipeline import EvalStorage
    storage = EvalStorage(settings.data_dir / "eval_pipeline")
    return {"history": storage.get_history(limit=limit)}


@router.get("/eval/averages")
def eval_averages(window: int = 10):
    """Get average evaluation scores."""
    from src.eval.pipeline import EvalStorage
    storage = EvalStorage(settings.data_dir / "eval_pipeline")
    return {"averages": storage.get_average_scores(window=window)}
