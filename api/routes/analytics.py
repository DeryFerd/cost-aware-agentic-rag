"""Cost analytics and export endpoints."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.database.semantic_cache import get_semantic_cache
from src.eval.prompt_regression import PromptRegressionTester
from src.generation.cost_tracker import CostTracker
from src.generation.prompt_registry import PromptRegistry
from src.ml.anomaly import AnomalyDetector
from src.ml.cost_analytics import CostAnalytics
from src.ml.cost_optimizer import CostOptimizer
from src.ml.export import QueryExporter
from src.ml.latency_tracker import LatencyTracker

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


@router.get("/latency/stats")
def latency_stats(hours: int = 24):
    """Return p50/p95/p99 latency per component and overall."""
    tracker = LatencyTracker()
    stats = tracker.get_stats(hours=hours)

    components: dict[str, dict[str, float]] = {}
    for comp, data in stats.get("components", {}).items():
        components[comp] = {
            "p50": data["p50_ms"],
            "p95": data["p95_ms"],
            "p99": data["p99_ms"],
        }

    overall_raw = stats.get("overall", {})
    overall = {
        "p50": overall_raw.get("p50_ms", 0.0),
        "p95": overall_raw.get("p95_ms", 0.0),
        "p99": overall_raw.get("p99_ms", 0.0),
    }

    return {**components, "overall": overall}


@router.get("/latency/recent")
def latency_recent(limit: int = 50):
    """Return recent latency entries."""
    tracker = LatencyTracker()
    entries = tracker.get_recent(limit=limit)
    return {"entries": entries, "count": len(entries)}


@router.get("/latency/trend")
def latency_trend(hours: int = 24, bucket_size: str = "1h"):
    """Return time-bucketed average latency."""
    tracker = LatencyTracker()
    raw_entries = tracker.get_recent(limit=10000)

    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    entries = [
        e for e in raw_entries
        if LatencyTracker._parse_timestamp(e.get("timestamp", "")) >= cutoff
    ]

    buckets: dict[str, list[float]] = defaultdict(list)
    for entry in entries:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
        except (KeyError, ValueError):
            continue
        bucket_key = ts.strftime("%Y-%m-%dT%H") + ":00:00"
        buckets[bucket_key].append(entry.get("total_ms", 0.0))

    trend = []
    for bucket_ts in sorted(buckets.keys()):
        values = buckets[bucket_ts]
        trend.append({
            "timestamp": bucket_ts,
            "avg_ms": round(sum(values) / len(values), 3),
            "count": len(values),
        })

    return {"trend": trend, "hours": hours, "bucket_size": bucket_size}


@router.get("/cache/stats")
def cache_stats():
    """Return semantic cache statistics."""
    cache = get_semantic_cache()
    stats = cache.stats()
    return {
        "hits": stats["hits"],
        "misses": stats["misses"],
        "hit_rate": round(stats["hit_rate"], 4),
        "total_entries": stats["entries"],
        "size_bytes": cache._cache_path.stat().st_size if cache._cache_path.exists() else 0,
    }


@router.get("/cost/savings")
def cost_savings():
    """Return cost savings from routing."""
    analytics = CostAnalytics()
    breakdown = analytics.routing_breakdown()
    efficiency = breakdown.get("routing_efficiency", {})

    history = CostTracker().load_history()
    saved = efficiency.get("estimated_savings_usd", 0.0)

    savings_by_model: dict[str, float] = defaultdict(float)
    for r in history:
        savings_by_model[r.model] += r.cost_usd

    return {
        "total_saved": round(saved, 6),
        "savings_by_model": dict(savings_by_model),
        "routing_efficiency": efficiency.get("savings_percentage", 0.0),
    }


@router.get("/cost/breakdown")
def cost_breakdown():
    """Return cost breakdown by complexity, model, and time."""
    optimizer = CostOptimizer()
    return optimizer.get_cost_breakdown_by_category()


@router.get("/cost/token-budgets")
def cost_token_budgets():
    """Return token budget usage."""
    tracker = CostTracker()
    history = tracker.load_history()

    total_tokens_in = 0
    total_tokens_out = 0
    by_model: dict[str, dict] = defaultdict(lambda: {"tokens_in": 0, "tokens_out": 0, "cost": 0.0})

    for r in history:
        total_tokens_in += r.tokens_in
        total_tokens_out += r.tokens_out
        by_model[r.model]["tokens_in"] += r.tokens_in
        by_model[r.model]["tokens_out"] += r.tokens_out
        by_model[r.model]["cost"] += r.cost_usd

    total_tokens = total_tokens_in + total_tokens_out

    budget_check = tracker.budget_check()
    headroom = budget_check.get("headroom", 0.0)

    return {
        "total_tokens": total_tokens,
        "by_model": {
            m: {
                "tokens_in": d["tokens_in"],
                "tokens_out": d["tokens_out"],
                "total_tokens": d["tokens_in"] + d["tokens_out"],
                "cost_usd": round(d["cost"], 6),
            }
            for m, d in by_model.items()
        },
        "budget_remaining": round(headroom, 6),
    }


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


# ── Prompt Versioning Endpoints ──────────────────────────────────────


class RollbackRequest(BaseModel):
    version: str


@router.get("/prompts")
def list_prompts():
    """List all registered prompts and their versions."""
    registry = PromptRegistry()
    return {"prompts": registry.list_all()}


@router.get("/prompts/{name}")
def get_prompt(name: str, version: str | None = None):
    """Get prompt details for a specific or current version."""
    registry = PromptRegistry()
    prompt = registry.get(name, version)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    versions = registry.list_versions(name)
    return {"prompt": prompt, "versions": versions}


@router.post("/prompts/{name}/rollback")
def rollback_prompt(name: str, body: RollbackRequest):
    """Rollback a prompt to a previous version."""
    registry = PromptRegistry()
    try:
        registry.rollback(name, body.version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"status": "ok", "prompt": name, "current_version": body.version}


@router.post("/prompts/{name}/regression")
def run_regression(name: str, versions: list[str] | None = None):
    """Run regression test on a prompt across versions."""
    tester = PromptRegressionTester()
    result = tester.test_prompt(name, versions)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/prompts/{name}/history")
def prompt_history(name: str):
    """Get regression test history for a prompt."""
    tester = PromptRegressionTester()
    return {"name": name, "history": tester.get_history(name)}


@router.get("/prompts/{name}/gates")
def check_gates(name: str, version: str):
    """Check if a prompt version passes CI quality gates."""
    tester = PromptRegressionTester()
    result = tester.check_gates(name, version)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
