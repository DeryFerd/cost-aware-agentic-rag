"""Anomaly detection for query patterns and system behavior."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from src.generation.cost_tracker import CostTracker


class AnomalyDetector:
    """Detect anomalies in query patterns, costs, and latency."""

    def __init__(self) -> None:
        self.tracker = CostTracker()

    def detect_anomalies(self, window_hours: int = 24) -> dict:
        """Detect anomalies in recent data."""
        history = self.tracker.load_history()
        if not history:
            return {"anomalies": [], "summary": {"total": 0}}

        # Filter to window
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        recent = []
        for r in history:
            try:
                ts = datetime.fromisoformat(r.timestamp.replace("Z", "+00:00"))
                if ts.replace(tzinfo=None) > cutoff:
                    recent.append(r)
            except (ValueError, TypeError):
                continue

        if not recent:
            return {"anomalies": [], "summary": {"total": 0}}

        anomalies = []

        # Check for cost anomalies
        cost_anomalies = self._detect_cost_anomalies(recent)
        anomalies.extend(cost_anomalies)

        # Check for latency anomalies
        latency_anomalies = self._detect_latency_anomalies(recent)
        anomalies.extend(latency_anomalies)

        # Check for query pattern anomalies
        pattern_anomalies = self._detect_pattern_anomalies(recent)
        anomalies.extend(pattern_anomalies)

        # Check for model routing anomalies
        routing_anomalies = self._detect_routing_anomalies(recent)
        anomalies.extend(routing_anomalies)

        return {
            "anomalies": anomalies,
            "summary": {
                "total": len(anomalies),
                "critical": len([a for a in anomalies if a["severity"] == "critical"]),
                "warning": len([a for a in anomalies if a["severity"] == "warning"]),
                "info": len([a for a in anomalies if a["severity"] == "info"]),
            },
            "window_hours": window_hours,
            "analyzed_queries": len(recent),
        }

    def _detect_cost_anomalies(self, records: list) -> list[dict]:
        """Detect cost anomalies (unusually high costs)."""
        anomalies = []
        costs = [r.cost_usd for r in records]

        if len(costs) < 3:
            return anomalies

        mean_cost = statistics.mean(costs)
        stdev_cost = statistics.stdev(costs) if len(costs) > 1 else 0

        for r in records:
            if stdev_cost > 0 and r.cost_usd > mean_cost + 2 * stdev_cost:
                severity = "critical" if r.cost_usd > mean_cost + 3 * stdev_cost else "warning"
                anomalies.append({
                    "type": "cost_spike",
                    "severity": severity,
                    "message": f"High cost: ${r.cost_usd:.6f} (avg: ${mean_cost:.6f})",
                    "query": r.query[:100],
                    "model": r.model,
                    "timestamp": r.timestamp,
                })

        return anomalies

    def _detect_latency_anomalies(self, records: list) -> list[dict]:
        """Detect latency anomalies (unusually slow responses)."""
        anomalies = []
        latencies = [r.latency_ms for r in records]

        if len(latencies) < 3:
            return anomalies

        mean_lat = statistics.mean(latencies)
        stdev_lat = statistics.stdev(latencies) if len(latencies) > 1 else 0

        for r in records:
            if stdev_lat > 0 and r.latency_ms > mean_lat + 2 * stdev_lat:
                anomalies.append({
                    "type": "latency_spike",
                    "severity": "warning",
                    "message": f"High latency: {r.latency_ms:.0f}ms (avg: {mean_lat:.0f}ms)",
                    "query": r.query[:100],
                    "model": r.model,
                    "timestamp": r.timestamp,
                })

        return anomalies

    def _detect_pattern_anomalies(self, records: list) -> list[dict]:
        """Detect unusual query patterns."""
        anomalies = []

        # Check for rapid successive queries (potential abuse)
        timestamps = []
        for r in records:
            try:
                ts = datetime.fromisoformat(r.timestamp.replace("Z", "+00:00"))
                timestamps.append(ts.replace(tzinfo=None))
            except (ValueError, TypeError):
                continue

        if len(timestamps) >= 2:
            timestamps.sort()
            for i in range(1, len(timestamps)):
                diff = (timestamps[i] - timestamps[i - 1]).total_seconds()
                if diff < 5:  # Less than 5 seconds between queries
                    anomalies.append({
                        "type": "rapid_queries",
                        "severity": "info",
                        "message": f"Rapid successive queries: {diff:.1f}s apart",
                        "timestamp": timestamps[i].isoformat(),
                    })
                    break  # Only report once

        return anomalies

    def _detect_routing_anomalies(self, records: list) -> list[dict]:
        """Detect unusual routing patterns."""
        anomalies = []

        # Count routing decisions
        by_model = defaultdict(int)
        for r in records:
            by_model[r.model] += 1

        total = len(records)
        if total < 5:
            return anomalies

        # Check if too many complex queries (potential routing issue)
        complex_count = sum(1 for r in records if "27b" in r.model)
        complex_ratio = complex_count / total

        if complex_ratio > 0.8:
            msg = f"High complex ratio: {complex_ratio:.0%} ({complex_count}/{total})"
            anomalies.append({
                "type": "routing_imbalance",
                "severity": "warning",
                "message": msg,
                "suggestion": "Check if classifier is working correctly",
            })

        return anomalies

    def get_health_metrics(self) -> dict:
        """Get system health metrics."""
        history = self.tracker.load_history()
        if not history:
            return {"status": "no_data", "metrics": {}}

        # Recent performance
        recent = history[-10:] if len(history) > 10 else history

        avg_cost = sum(r.cost_usd for r in recent) / len(recent)
        avg_latency = sum(r.latency_ms for r in recent) / len(recent)

        # Error rate (queries with very high latency or cost)
        error_count = sum(
            1 for r in recent
            if r.latency_ms > 30000 or r.cost_usd > 0.1
        )
        error_rate = error_count / len(recent)

        # Determine health status
        if error_rate > 0.2:
            status = "degraded"
        elif avg_latency > 15000:
            status = "slow"
        else:
            status = "healthy"

        return {
            "status": status,
            "metrics": {
                "avg_cost": round(avg_cost, 6),
                "avg_latency_ms": round(avg_latency, 1),
                "error_rate": round(error_rate, 3),
                "total_queries": len(history),
                "recent_queries": len(recent),
            },
        }
