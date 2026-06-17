"""Cost analytics and export endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import FileResponse

from src.ml.cost_analytics import CostAnalytics
from src.ml.export import QueryExporter
from src.ml.anomaly import AnomalyDetector
from src.generation.cost_tracker import CostTracker

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/cost/summary")
def cost_summary():
    """Get cost summary."""
    tracker = CostTracker()
    return tracker.summary()


@router.get("/cost/budget")
def cost_budget():
    """Check budget status."""
    tracker = CostTracker()
    return tracker.budget_check()


@router.get("/analytics/models")
def model_comparison():
    """Compare performance across models."""
    analytics = CostAnalytics()
    return analytics.model_comparison()


@router.get("/analytics/routing")
def routing_breakdown():
    """Analyze routing efficiency and breakdown."""
    analytics = CostAnalytics()
    return analytics.routing_breakdown()


@router.get("/analytics/trend")
def cost_trend(days: int = 7):
    """Get cost trend over time."""
    analytics = CostAnalytics()
    return analytics.cost_trend(days=days)


@router.get("/analytics/tokens")
def cost_per_token():
    """Analyze cost efficiency per token."""
    analytics = CostAnalytics()
    return analytics.cost_per_token()


@router.get("/analytics/anomalies")
def detect_anomalies(window_hours: int = 24):
    """Detect anomalies in recent data."""
    detector = AnomalyDetector()
    return detector.detect_anomalies(window_hours=window_hours)


@router.get("/health/metrics")
def health_metrics():
    """Get system health metrics."""
    detector = AnomalyDetector()
    return detector.get_health_metrics()


@router.get("/export/query")
def export_query(
    query: str,
    answer: str,
    model_used: str = "unknown",
    cost_usd: float = 0.0,
    latency_ms: float = 0.0,
    steps_count: int = 0,
):
    """Export a single query result to PDF."""
    exporter = QueryExporter()
    filepath = exporter.export_query_pdf(
        query=query,
        answer=answer,
        citations=[],
        model_used=model_used,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        steps_count=steps_count,
    )
    return FileResponse(path=str(filepath), filename=filepath.name, media_type="application/pdf")


@router.get("/export/analytics")
def export_analytics():
    """Export analytics summary to PDF."""
    analytics = CostAnalytics()
    data = {
        "models": analytics.model_comparison().get("models", []),
        "routing_efficiency": analytics.routing_breakdown().get("routing_efficiency", {}),
    }
    exporter = QueryExporter()
    filepath = exporter.export_analytics_pdf(data)
    return FileResponse(path=str(filepath), filename=filepath.name, media_type="application/pdf")


@router.get("/export/queries/csv")
def export_queries_csv():
    """Export query history to CSV."""
    tracker = CostTracker()
    history = tracker.load_history()

    queries = []
    for r in history:
        queries.append({
            "query": r.query,
            "answer": "",
            "model_used": r.model,
            "complexity": r.complexity,
            "cost_usd": r.cost_usd,
            "latency_ms": r.latency_ms,
            "citations": [],
            "timestamp": r.timestamp,
        })

    exporter = QueryExporter()
    filepath = exporter.export_queries_csv(queries)
    return FileResponse(path=str(filepath), filename=filepath.name, media_type="text/csv")


@router.get("/export/list")
def list_exports():
    """List all exported files."""
    exporter = QueryExporter()
    return {"exports": exporter.list_exports()}
