"""Model A/B testing framework for comparing primary and challenger models.

Provides probabilistic routing, per-variant metrics tracking, and analytics
to evaluate whether a challenger model outperforms the primary.
"""

from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config import settings
from src.ml.routing import RoutingResult

logger = logging.getLogger(__name__)

METRICS_DIR = settings.data_dir / "metrics"
AB_LOG_FILE = METRICS_DIR / "ab_test_log.jsonl"


# ── Configuration ──────────────────────────────────────────────────


@dataclass
class ABTestConfig:
    """Configuration for an A/B test between two models."""

    model_a: str = settings.ollama_simple_model
    model_b: str = settings.ollama_complex_model
    traffic_split: float = 0.1
    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_a": self.model_a,
            "model_b": self.model_b,
            "traffic_split": self.traffic_split,
            "enabled": self.enabled,
        }


# ── Routing ────────────────────────────────────────────────────────


class ABTestRouter:
    """Probabilistically route a fraction of queries to the challenger model."""

    def __init__(self, config: ABTestConfig | None = None) -> None:
        self.config = config or ABTestConfig()
        self._dir = METRICS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._log_file = AB_LOG_FILE

    def route(self, query: str, routing_result: RoutingResult) -> RoutingResult:
        """Potentially reroute to model B based on the configured traffic split.

        Returns a (possibly modified) RoutingResult.
        """
        if not self.config.enabled:
            return routing_result

        variant = "A"
        assigned_model = self.config.model_a

        if random.random() < self.config.traffic_split:
            variant = "B"
            assigned_model = self.config.model_b

        ab_result = RoutingResult(
            complexity=routing_result.complexity,
            confidence=routing_result.confidence,
            model=assigned_model,
            cost_estimate=routing_result.cost_estimate,
            method=routing_result.method,
        )

        self._log_routing(query, variant, routing_result, ab_result)
        return ab_result

    def _log_routing(
        self,
        query: str,
        variant: str,
        original: RoutingResult,
        assigned: RoutingResult,
    ) -> None:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "query": query,
            "variant": variant,
            "original_model": original.model,
            "assigned_model": assigned.model,
            "complexity": assigned.complexity,
        }
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as exc:
            logger.error("Failed to write A/B routing log: %s", exc)


# ── Analytics ──────────────────────────────────────────────────────


@dataclass
class _VariantStats:
    query_count: int = 0
    total_latency_ms: float = 0.0
    total_cost: float = 0.0
    latencies: list[float] = field(default_factory=list)


class ABTestAnalytics:
    """Compare metrics between A and B variants."""

    def __init__(self, metrics_dir: Path | None = None) -> None:
        self._dir = metrics_dir or METRICS_DIR
        self._log_file = self._dir / "ab_test_log.jsonl"

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self._log_file.exists():
            return []
        entries: list[dict[str, Any]] = []
        try:
            with open(self._log_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load A/B test log: %s", exc)
        return entries

    def get_results(self) -> dict[str, Any]:
        """Return comparative metrics for variants A and B.

        Expected log entries contain at least ``variant`` and ``timestamp``.
        Latency and cost are pulled from ``latency.jsonl`` when available.
        """
        entries = self._load_entries()
        if not entries:
            return {"enabled": False, "variants": {}, "total_entries": 0}

        # Load latency data for enrichment
        latency_file = self._dir / "latency.jsonl"
        latency_entries: list[dict[str, Any]] = []
        if latency_file.exists():
            try:
                with open(latency_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            latency_entries.append(json.loads(line))
            except (OSError, json.JSONDecodeError):
                pass

        variant_stats: dict[str, _VariantStats] = defaultdict(_VariantStats)

        for entry in entries:
            v = entry.get("variant", "A")
            variant_stats[v].query_count += 1

        # Enrich with latency data when query text matches
        query_latency: dict[str, dict[str, float]] = {}
        for le in latency_entries:
            q = le.get("query", "")
            if q:
                query_latency[q] = {
                    "total_ms": le.get("total_ms", 0),
                    "components": le.get("components", {}),
                }

        for entry in entries:
            v = entry.get("variant", "A")
            q = entry.get("query", "")
            if q in query_latency:
                stats = variant_stats[v]
                lat = query_latency[q]["total_ms"]
                stats.total_latency_ms += lat
                stats.latencies.append(lat)

        # Build response
        variants: dict[str, dict[str, Any]] = {}
        for v in ("A", "B"):
            s = variant_stats[v]
            avg_lat = (s.total_latency_ms / s.query_count) if s.query_count > 0 else 0.0
            sorted_lats = sorted(s.latencies)
            variants[v] = {
                "model": (
                    settings.ollama_simple_model if v == "A" else settings.ollama_complex_model
                ),
                "query_count": s.query_count,
                "avg_latency_ms": round(avg_lat, 3),
                "p50_latency_ms": (
                    round(self._percentile(sorted_lats, 50), 3) if sorted_lats else 0.0
                ),
                "p95_latency_ms": (
                    round(self._percentile(sorted_lats, 95), 3) if sorted_lats else 0.0
                ),
            }

        total = sum(s.query_count for s in variant_stats.values())
        split_b = (variant_stats["B"].query_count / total * 100) if total > 0 else 0.0

        return {
            "enabled": True,
            "total_entries": total,
            "actual_split_b_pct": round(split_b, 1),
            "variants": variants,
        }

    @staticmethod
    def _percentile(sorted_vals: list[float], p: float) -> float:
        if not sorted_vals:
            return 0.0
        k = (len(sorted_vals) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(sorted_vals) - 1)
        d = k - f
        return sorted_vals[f] + d * (sorted_vals[c] - sorted_vals[f])
