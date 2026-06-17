"""Feedback and suggestions endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.models import FeedbackRequest, FeedbackStats
from src.ml.feedback import store_feedback, get_feedback_stats, get_recent_feedback
from src.ml.suggestions import QuerySuggestion

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/feedback")
def feedback(req: FeedbackRequest):
    """Submit feedback for a query response."""
    entry = store_feedback(
        query=req.query,
        answer=req.answer,
        rating=req.rating,
        comment=req.comment,
    )
    return {"status": "stored", "id": entry["id"]}


@router.get("/feedback/stats", response_model=FeedbackStats)
def feedback_stats() -> FeedbackStats:
    """Get aggregated feedback statistics."""
    stats = get_feedback_stats()
    return FeedbackStats(**stats)


@router.get("/feedback/recent")
def feedback_recent(limit: int = 20):
    """Get recent feedback entries."""
    return {"feedback": get_recent_feedback(limit)}


@router.get("/suggestions")
def get_suggestions(limit: int = 5):
    """Get query suggestions."""
    suggestion_engine = QuerySuggestion()
    return {"suggestions": suggestion_engine.get_suggestions(limit=limit)}


@router.get("/suggestions/related")
def get_related_queries(query: str, limit: int = 3):
    """Get queries related to the input query."""
    suggestion_engine = QuerySuggestion()
    return {"related": suggestion_engine.get_related_queries(query, limit=limit)}
