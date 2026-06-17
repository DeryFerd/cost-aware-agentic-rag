"""Per-component latency tracking for the RAG pipeline.

Records timing for routing, retrieval, reranking, generation, and guardrails.
Persists to data/metrics/latency.jsonl and provides aggregate statistics.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

METRICS_DIR = settings.data_dir / "metrics"
LATENCY_FILE = METRICS_DIR / "latency.jsonl"

COMPONENTS = ("routing", "retrieval", "reranking", "generation", "guardrails")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _percentile(sorted_vals: list[float], p: float) -> float:
    """Compute the p-th percentile from a pre-sorted list."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    d = k - f
    return sorted_vals[f] + d * (sorted_vals[c] - sorted_vals[f])


class LatencyTracker:
    """Track per-component and overall pipeline latency."""

    def __init__(self, metrics_dir: Path | None = None) -> None:
        self._dir = metrics_dir or METRICS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "latency.jsonl"
        self._active: dict[str, float] = {}

    # ── Timing ──────────────────────────────────────────────────────

    def start(self, component: str) -> None:
        """Start timing a component."""
        if component in self._active:
            logger.warning("Overlapping start for component '%s'", component)
        self._active[component] = time.perf_counter()

    def end(self, component: str) -> float:
        """End timing a component and return elapsed milliseconds."""
        if component not in self._active:
            logger.warning("end() called for '%s' without a matching start()", component)
            return 0.0
        elapsed_ms = (time.perf_counter() - self._active.pop(component)) * 1000
        return round(elapsed_ms, 3)

    # ── Recording ───────────────────────────────────────────────────

    def record(
        self,
        query: str,
        components: dict[str, float],
        total_ms: float,
    ) -> None:
        """Append a full pipeline timing entry to the JSONL file."""
        entry: dict[str, Any] = {
            "timestamp": _now_iso(),
            "query": query,
            "total_ms": round(total_ms, 3),
            "components": components,
        }
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as exc:
            logger.error("Failed to write latency record: %s", exc)

    # ── Reading ─────────────────────────────────────────────────────

    def _load_entries(self) -> list[dict[str, Any]]:
        """Load all entries from the JSONL file."""
        if not self._file.exists():
            return []
        entries: list[dict[str, Any]] = []
        try:
            with open(self._file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load latency entries: %s", exc)
        return entries

    def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return the most recent entries (newest last)."""
        return self._load_entries()[-limit:]

    def get_stats(self, hours: int = 24) -> dict[str, Any]:
        """Return aggregate latency stats for the given time window."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        entries = [
            e
            for e in self._load_entries()
            if self._parse_timestamp(e.get("timestamp", "")) >= cutoff
        ]
        if not entries:
            return {"hours": hours, "total_queries": 0, "components": {}, "overall": {}}

        # Per-component stats
        comp_latencies: dict[str, list[float]] = defaultdict(list)
        total_latencies: list[float] = []

        for entry in entries:
            total_latencies.append(entry.get("total_ms", 0))
            for comp, ms in entry.get("components", {}).items():
                comp_latencies[comp].append(ms)

        comp_stats: dict[str, dict[str, float]] = {}
        for comp, vals in comp_latencies.items():
            vals.sort()
            comp_stats[comp] = {
                "count": len(vals),
                "avg_ms": round(sum(vals) / len(vals), 3),
                "min_ms": round(vals[0], 3),
                "max_ms": round(vals[-1], 3),
                "p50_ms": round(_percentile(vals, 50), 3),
                "p95_ms": round(_percentile(vals, 95), 3),
                "p99_ms": round(_percentile(vals, 99), 3),
            }

        total_latencies.sort()
        overall = {
            "count": len(total_latencies),
            "avg_ms": round(sum(total_latencies) / len(total_latencies), 3),
            "p50_ms": round(_percentile(total_latencies, 50), 3),
            "p95_ms": round(_percentile(total_latencies, 95), 3),
            "p99_ms": round(_percentile(total_latencies, 99), 3),
        }

        return {
            "hours": hours,
            "total_queries": len(entries),
            "components": comp_stats,
            "overall": overall,
        }

    @staticmethod
    def _parse_timestamp(ts: str) -> datetime:
        """Parse an ISO timestamp, returning epoch on failure."""
        try:
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return datetime.fromtimestamp(0, tz=UTC)


# ── Context Manager ────────────────────────────────────────────────

_tracker: LatencyTracker | None = None


def _get_tracker() -> LatencyTracker:
    global _tracker
    if _tracker is None:
        _tracker = LatencyTracker()
    return _tracker


@contextmanager
def timed(component: str) -> Generator[None, None, None]:
    """Context manager that times a pipeline component.

    Usage::

        with timed("retrieval"):
            results = retriever.retrieve(query)
    """
    tracker = _get_tracker()
    tracker.start(component)
    try:
        yield
    finally:
        tracker.end(component)


# ── Convenience singleton ──────────────────────────────────────────


def get_latency_tracker() -> LatencyTracker:
    """Return the module-level LatencyTracker singleton."""
    return _get_tracker()
