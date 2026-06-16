"""Cost analytics for model comparison and optimization insights."""

from __future__ import annotations

from collections import defaultdict

from src.generation.cost_tracker import CostTracker


class CostAnalytics:
    """Analyze cost patterns and provide model comparison insights."""

    def __init__(self) -> None:
        self.tracker = CostTracker()

    def model_comparison(self) -> dict:
        """Compare performance across models."""
        history = self.tracker.load_history()
        if not history:
            return {"models": [], "summary": {}}

        # Aggregate by model
        by_model: dict[str, list] = defaultdict(list)
        for r in history:
            by_model[r.model].append(r)

        models = []
        for model_name, records in by_model.items():
            costs = [r.cost_usd for r in records]
            latencies = [r.latency_ms for r in records]

            models.append({
                "model": model_name,
                "query_count": len(records),
                "total_cost": round(sum(costs), 6),
                "avg_cost": round(sum(costs) / len(costs), 6),
                "min_cost": round(min(costs), 6),
                "max_cost": round(max(costs), 6),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 1),
                "p50_latency_ms": round(sorted(latencies)[len(latencies) // 2], 1),
                "p95_latency_ms": (
                    round(sorted(latencies)[int(len(latencies) * 0.95)], 1)
                    if len(latencies) > 1
                    else round(latencies[0], 1)
                ),
            })

        # Sort by query count descending
        models.sort(key=lambda m: m["query_count"], reverse=True)

        return {
            "models": models,
            "total_queries": len(history),
            "total_cost": round(sum(r.cost_usd for r in history), 6),
        }

    def routing_breakdown(self) -> dict:
        """Analyze how queries are routed across complexity levels."""
        history = self.tracker.load_history()
        if not history:
            return {"complexity": {}, "routing_efficiency": {}}

        by_complexity: dict[str, list] = defaultdict(list)
        for r in history:
            by_complexity[r.complexity].append(r)

        complexity = {}
        for level, records in by_complexity.items():
            costs = [r.cost_usd for r in records]
            complexity[level] = {
                "count": len(records),
                "percentage": round(len(records) / len(history) * 100, 1),
                "avg_cost": round(sum(costs) / len(costs), 6),
                "total_cost": round(sum(costs), 6),
                "avg_latency_ms": round(sum(r.latency_ms for r in records) / len(records), 1),
            }

        # Calculate routing efficiency (savings vs always using expensive model)
        simple_queries = by_complexity.get("simple", [])
        complex_queries = by_complexity.get("complex", [])

        # Estimate cost if all queries used complex model
        avg_complex_cost = 0.0
        if complex_queries:
            avg_complex_cost = sum(r.cost_usd for r in complex_queries) / len(complex_queries)

        # Use a reasonable estimate for simple model cost
        avg_simple_cost = 0.0
        if simple_queries:
            avg_simple_cost = sum(r.cost_usd for r in simple_queries) / len(simple_queries)

        # Estimate savings: simple queries routed to simple model save (complex_cost - simple_cost)
        estimated_savings = 0.0
        if simple_queries and avg_complex_cost > 0:
            estimated_savings = len(simple_queries) * (avg_complex_cost - avg_simple_cost)

        return {
            "complexity": complexity,
            "routing_efficiency": {
                "simple_queries_routed": len(simple_queries),
                "complex_queries_routed": len(complex_queries),
                "estimated_savings_usd": round(max(0, estimated_savings), 6),
                "savings_percentage": round(
                    (estimated_savings / (len(history) * avg_complex_cost) * 100)
                    if history and avg_complex_cost > 0
                    else 0,
                    1,
                ),
            },
        }

    def cost_trend(self, days: int = 7) -> dict:
        """Get cost trend over time."""
        history = self.tracker.load_history()
        if not history:
            return {"daily": [], "period": days}

        # Group by date
        daily: dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "count": 0, "models": set()})

        for r in history:
            try:
                date = r.timestamp[:10]  # YYYY-MM-DD
            except (IndexError, TypeError):
                continue
            daily[date]["cost"] += r.cost_usd
            daily[date]["count"] += 1
            daily[date]["models"].add(r.model)

        # Convert to sorted list
        daily_list = []
        for date in sorted(daily.keys())[-days:]:
            entry = daily[date]
            daily_list.append({
                "date": date,
                "cost": round(entry["cost"], 6),
                "queries": entry["count"],
                "models_used": len(entry["models"]),
            })

        return {
            "daily": daily_list,
            "period": days,
            "total_cost": round(sum(d["cost"] for d in daily_list), 6),
            "total_queries": sum(d["queries"] for d in daily_list),
        }

    def cost_per_token(self) -> dict:
        """Analyze cost efficiency per token."""
        history = self.tracker.load_history()
        if not history:
            return {"by_model": [], "overall": {}}

        by_model: dict[str, dict] = defaultdict(
            lambda: {"cost": 0.0, "tokens_in": 0, "tokens_out": 0, "count": 0}
        )

        for r in history:
            by_model[r.model]["cost"] += r.cost_usd
            by_model[r.model]["tokens_in"] += r.tokens_in
            by_model[r.model]["tokens_out"] += r.tokens_out
            by_model[r.model]["count"] += 1

        models = []
        total_cost = 0.0
        total_tokens = 0

        for model_name, data in by_model.items():
            total_in = data["tokens_in"]
            total_out = data["tokens_out"]
            total_tok = total_in + total_out

            cost_per_1k = (data["cost"] / total_tok * 1000) if total_tok > 0 else 0

            models.append({
                "model": model_name,
                "total_cost": round(data["cost"], 6),
                "total_tokens": total_tok,
                "cost_per_1k_tokens": round(cost_per_1k, 6),
                "avg_tokens_per_query": (
                    round(total_tok / data["count"]) if data["count"] > 0 else 0
                ),
            })

            total_cost += data["cost"]
            total_tokens += total_tok

        overall_cost_per_1k = (total_cost / total_tokens * 1000) if total_tokens > 0 else 0

        return {
            "by_model": models,
            "overall": {
                "total_cost": round(total_cost, 6),
                "total_tokens": total_tokens,
                "cost_per_1k_tokens": round(overall_cost_per_1k, 6),
            },
        }
