"""Online evaluation endpoints — monitor production query quality.

Uses LLM-as-Judge to sample and evaluate production traffic.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.eval.online_eval import online_evaluator

logger = logging.getLogger(__name__)
router = APIRouter()


class EvalSampleRequest(BaseModel):
    query: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    model_used: str = Field(default="unknown")
    complexity: str = Field(default="unknown")
    latency_ms: float = Field(default=0.0)
    cost_usd: float = Field(default=0.0)


@router.get("/online-eval/stats")
async def eval_stats():
    """Get online evaluation statistics."""
    stats = online_evaluator.get_stats()
    return stats


@router.post("/online-eval/evaluate")
async def evaluate_sample(req: EvalSampleRequest):
    """Manually trigger evaluation for a specific query/answer pair."""
    result = online_evaluator.sample_and_evaluate(
        query=req.query,
        answer=req.answer,
        model_used=req.model_used,
        complexity=req.complexity,
        latency_ms=req.latency_ms,
        cost_usd=req.cost_usd,
    )
    if result is None:
        raise HTTPException(status_code=500, detail="Evaluation failed")
    return result.__dict__


@router.get("/online-eval/results")
async def eval_results(
    limit: int = 20,
    min_score: float | None = None,
):
    """Get recent online evaluation results, optionally filtered by score."""
    # This queries the SQLite eval database
    try:
        from src.eval.db import get_db
        db = get_db()
        conn = db.connection
        cursor = conn.execute(
            "SELECT * FROM online_eval_results ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        if min_score is not None:
            results = [r for r in results if r.get("overall_score", 0) >= min_score]
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.warning(f"Failed to query eval results: {e}")
        return {"results": [], "count": 0}
