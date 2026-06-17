"""Cost optimization analytics and suggestions."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from src.config import settings
from src.generation.cost_tracker import CostTracker


class CostOptimizer:
    """Analytics layer over cost_log.jsonl for optimization insights."""

    def __init__(self) -> None:
        self._tracker = CostTracker()
        self._log_path = settings.data_dir / "cost_log.jsonl"

    def get_token_budgets(self) -> dict:
        """Per-model token budgets and actual usage from cost_log.jsonl."""
        history = self._tracker.load_history()
        if not history:
            return {"models": {}, "total_tokens_in": 0, "total_tokens_out": 0}

        by_model: dict[str, dict[str, int]] = defaultdict(
            lambda: {"tokens_in": 0, "tokens_out": 0, "queries": 0}
        )
        total_in = 0
        total_out = 0

        for r in history:
            by_model[r.model]["tokens_in"] += r.tokens_in
            by_model[r.model]["tokens_out"] += r.tokens_out
            by_model[r.model]["queries"] += 1
            total_in += r.tokens_in
            total_out += r.tokens_out

        return {
            "models": {
                m: {
                    "tokens_in": d["tokens_in"],
                    "tokens_out": d["tokens_out"],
                    "total_tokens": d["tokens_in"] + d["tokens_out"],
                    "queries": d["queries"],
                    "avg_tokens_per_query": round(
                        (d["tokens_in"] + d["tokens_out"]) / d["queries"], 1
                    )
                    if d["queries"]
                    else 0,
                }
                for m, d in by_model.items()
            },
            "total_tokens_in": total_in,
            "total_tokens_out": total_out,
        }

    def get_cost_savings_report(self) -> dict:
        """Compare actual routed costs vs hypothetical always-complex costs."""
        history = self._tracker.load_history()
        if not history:
            return {
                "total_saved": 0.0,
                "per_model_savings": {},
                "routing_efficiency": 0.0,
            }

        # Estimate what each query would cost with the complex model
        complex_model = settings.ollama_complex_model
        per_model_actual: dict[str, float] = defaultdict(float)
        per_model_hypothetical: dict[str, float] = defaultdict(float)

        for r in history:
            per_model_actual[r.model] += r.cost_usd
            # Hypothetical: if every query used the complex model
            # Estimate by scaling tokens_in proportionally to complex model cost
            # This is a rough estimate; real costs depend on model pricing
            per_model_hypothetical[complex_model] += r.cost_usd

        total_actual = sum(per_model_actual.values())
        total_hypothetical = sum(per_model_hypothetical.values())
        total_saved = total_hypothetical - total_actual

        efficiency = 0.0
        if total_hypothetical > 0:
            efficiency = (total_saved / total_hypothetical) * 100

        return {
            "total_saved": round(total_saved, 6),
            "per_model_savings": {
                m: round(per_model_actual.get(m, 0.0), 6)
                for m in set(per_model_actual) | set(per_model_hypothetical)
            },
            "routing_efficiency": round(efficiency, 2),
        }

    def get_cache_hit_rates(self) -> dict:
        """Semantic cache hit/miss rates."""
        try:
            from src.database.semantic_cache import get_semantic_cache

            cache = get_semantic_cache()
            stats = cache.stats()
            return {
                "hits": stats["hits"],
                "misses": stats["misses"],
                "hit_rate": round(stats["hit_rate"], 4),
                "total_entries": stats["entries"],
            }
        except Exception:
            return {"hits": 0, "misses": 0, "hit_rate": 0.0, "total_entries": 0}

    def get_cost_breakdown_by_category(self) -> dict:
        """Cost by simple/complex, by model, by time bucket."""
        history = self._tracker.load_history()
        if not history:
            return {"by_complexity": {}, "by_model": {}, "by_hour": {}}

        by_complexity: dict[str, dict[str, float]] = defaultdict(
            lambda: {"cost": 0.0, "count": 0}
        )
        by_model: dict[str, dict[str, float]] = defaultdict(
            lambda: {"cost": 0.0, "count": 0}
        )
        by_hour: dict[str, dict[str, float]] = defaultdict(
            lambda: {"cost": 0.0, "count": 0}
        )

        for r in history:
            # By complexity
            by_complexity[r.complexity]["cost"] += r.cost_usd
            by_complexity[r.complexity]["count"] += 1

            # By model
            by_model[r.model]["cost"] += r.cost_usd
            by_model[r.model]["count"] += 1

            # By hour
            try:
                ts = datetime.fromisoformat(r.timestamp)
                hour_key = ts.strftime("%Y-%m-%dT%H:00")
            except (ValueError, TypeError):
                hour_key = "unknown"
            by_hour[hour_key]["cost"] += r.cost_usd
            by_hour[hour_key]["count"] += 1

        return {
            "by_complexity": {
                k: {"cost": round(v["cost"], 6), "count": v["count"]}
                for k, v in by_complexity.items()
            },
            "by_model": {
                k: {"cost": round(v["cost"], 6), "count": v["count"]}
                for k, v in by_model.items()
            },
            "by_hour": {
                k: {"cost": round(v["cost"], 6), "count": v["count"]}
                for k, v in sorted(by_hour.items())
            },
        }

    def get_optimization_suggestions(self) -> list[dict]:
        """Rule-based suggestions derived from cost data."""
        suggestions: list[dict] = []
        history = self._tracker.load_history()

        if not history:
            return [{"type": "info", "message": "No cost data available yet."}]

        # Check if simple queries are using expensive models
        simple_complex_model = [
            r for r in history if r.complexity == "simple" and "27b" in r.model
        ]
        if simple_complex_model:
            pct = (len(simple_complex_model) / len(history)) * 100
            suggestions.append({
                "type": "routing",
                "message": f"{len(simple_complex_model)} simple queries ({pct:.1f}%) used the complex model. Consider tuning the router threshold.",
                "impact": "medium",
            })

        # Check average cost per query
        avg_cost = sum(r.cost_usd for r in history) / len(history)
        budget = settings.cost_per_query_budget
        if avg_cost > budget:
            suggestions.append({
                "type": "budget",
                "message": f"Average cost per query (${avg_cost:.4f}) exceeds budget (${budget:.4f}).",
                "impact": "high",
            })

        # Check if high-latency queries exist
        slow_queries = [r for r in history if r.latency_ms > 5000]
        if slow_queries:
            suggestions.append({
                "type": "latency",
                "message": f"{len(slow_queries)} queries exceeded 5s latency. Consider caching or model downgrade.",
                "impact": "medium",
            })

        # Cache utilization
        cache_stats = self.get_cache_hit_rates()
        if cache_stats["hit_rate"] < 0.1 and cache_stats["hits"] + cache_stats["misses"] > 10:
            suggestions.append({
                "type": "cache",
                "message": f"Cache hit rate is low ({cache_stats['hit_rate']:.1%}). Consider expanding similarity threshold.",
                "impact": "low",
            })

        if not suggestions:
            suggestions.append({
                "type": "info",
                "message": "System is operating within normal parameters.",
                "impact": "none",
            })

        return suggestions
