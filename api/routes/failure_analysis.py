"""Failure analysis endpoints."""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter

from src.eval.db import get_runs

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/failures")
def get_failure_analysis():
    """Return failure analysis from the latest eval run."""
    runs = get_runs(limit=10)
    completed_runs = [r for r in runs if r.get("status") == "completed"]

    if not completed_runs:
        return {
            "total_queries": 0,
            "total_failures": 0,
            "failure_rate": 0.0,
            "top_categories": [],
            "failures_by_bucket": {},
            "failures": [],
        }

    latest_run = completed_runs[0]
    run_id = latest_run["run_id"]
    results = latest_run.get("results", [])

    total_queries = len(results)
    failures = [r for r in results if r.get("bucket") != "correct"]
    total_failures = len(failures)
    failure_rate = (total_failures / total_queries * 100) if total_queries > 0 else 0.0

    # Group by bucket
    failures_by_bucket: dict[str, list[dict]] = defaultdict(list)
    for f in failures:
        bucket = f.get("bucket", "unknown")
        failures_by_bucket[bucket].append({
            "query": f.get("query", ""),
            "expected": f.get("expected_answer", ""),
            "actual": f.get("actual_answer", ""),
            "model_used": f.get("model_used", ""),
            "latency_ms": f.get("latency_ms", 0.0),
            "cost_usd": f.get("cost_usd", 0.0),
            "bucket": bucket,
            "score": f.get("score", 0.0),
        })

    # Top failure categories by count
    top_categories = sorted(
        [{"category": k, "count": len(v)} for k, v in failures_by_bucket.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    return {
        "run_id": run_id,
        "run_timestamp": latest_run.get("timestamp", ""),
        "total_queries": total_queries,
        "total_failures": total_failures,
        "failure_rate": round(failure_rate, 2),
        "top_categories": top_categories,
        "failures_by_bucket": dict(failures_by_bucket),
        "failures": failures_by_bucket.get("wrong_answer", [])
            + failures_by_bucket.get("no_answer", [])
            + failures_by_bucket.get("partial", []),
    }


@router.get("/failures/trends")
def get_failure_trends():
    """Return failure trends across eval runs."""
    runs = get_runs(limit=50)
    completed_runs = [r for r in runs if r.get("status") == "completed"]

    if len(completed_runs) < 1:
        return {"trends": [], "latest_run": None, "previous_run": None}

    # Build per-run failure stats (oldest first)
    run_stats = []
    for run in reversed(completed_runs):
        results = run.get("results", [])
        total = len(results)
        failures = [r for r in results if r.get("bucket") != "correct"]
        fail_count = len(failures)
        fail_rate = (fail_count / total * 100) if total > 0 else 0.0

        # Bucket breakdown
        bucket_counts: dict[str, int] = defaultdict(int)
        for f in failures:
            bucket_counts[f.get("bucket", "unknown")] += 1

        run_stats.append({
            "run_id": run["run_id"],
            "timestamp": run.get("timestamp", ""),
            "total_queries": total,
            "failures": fail_count,
            "failure_rate": round(fail_rate, 2),
            "buckets": dict(bucket_counts),
        })

    # Compute trend between consecutive runs
    trends = []
    for i in range(1, len(run_stats)):
        prev = run_stats[i - 1]
        curr = run_stats[i]
        delta = curr["failure_rate"] - prev["failure_rate"]
        trends.append({
            "run_id": curr["run_id"],
            "timestamp": curr["timestamp"],
            "failure_rate": curr["failure_rate"],
            "delta": round(delta, 2),
            "improved": delta < 0,
            "total_queries": curr["total_queries"],
            "failures": curr["failures"],
            "buckets": curr["buckets"],
        })

    latest = run_stats[-1] if run_stats else None
    previous = run_stats[-2] if len(run_stats) >= 2 else None

    return {
        "trends": trends,
        "run_stats": run_stats,
        "latest_run": latest,
        "previous_run": previous,
    }