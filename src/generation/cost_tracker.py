"""Cost tracking for LLM queries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

from src.config import settings


@dataclass
class QueryCostRecord:
    query: str
    model: str
    complexity: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    timestamp: str = ""


class CostTracker:
    """Track per-query costs and generate analytics."""

    def __init__(self) -> None:
        self.records: list[QueryCostRecord] = []
        self._log_path = settings.data_dir / "cost_log.jsonl"

    def record(self, entry: QueryCostRecord) -> None:
        if not entry.timestamp:
            entry.timestamp = datetime.now(timezone.utc).isoformat()
        self.records.append(entry)
        self._persist(entry)

    def _persist(self, entry: QueryCostRecord) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def load_history(self) -> list[QueryCostRecord]:
        if not self._log_path.exists():
            return []
        records = []
        with open(self._log_path) as f:
            for line in f:
                if line.strip():
                    records.append(QueryCostRecord(**json.loads(line)))
        return records

    def summary(self) -> dict:
        history = self.load_history()
        if not history:
            return {
                "total_queries": 0,
                "total_cost": 0.0,
                "avg_cost_per_query": 0.0,
                "cost_by_model": {},
                "avg_latency_ms": 0.0,
            }

        total_cost = sum(r.cost_usd for r in history)
        model_costs: dict[str, float] = {}
        for r in history:
            model_costs[r.model] = model_costs.get(r.model, 0) + r.cost_usd

        return {
            "total_queries": len(history),
            "total_cost": round(total_cost, 6),
            "avg_cost_per_query": round(total_cost / len(history), 6),
            "cost_by_model": model_costs,
            "avg_latency_ms": round(
                sum(r.latency_ms for r in history) / len(history), 1
            ),
        }

    def budget_check(self, budget: float | None = None) -> dict:
        budget = budget or settings.cost_per_query_budget
        history = self.load_history()
        recent = history[-10:] if len(history) > 10 else history

        recent_avg = (
            sum(r.cost_usd for r in recent) / len(recent) if recent else 0
        )

        return {
            "budget_per_query": budget,
            "recent_avg_cost": round(recent_avg, 6),
            "under_budget": recent_avg <= budget,
            "headroom": round(budget - recent_avg, 6),
        }
