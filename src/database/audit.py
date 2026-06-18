"""Audit logging for admin actions, auth events, and queries."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

AUDIT_DIR = settings.data_dir / "audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_FILE = AUDIT_DIR / "audit.jsonl"


class AuditLogger:
    """Append-only JSONL audit log with query and summary methods."""

    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path or AUDIT_FILE

    # ── Write ──────────────────────────────────────────────────────

    def log_event(
        self,
        actor: str,
        action: str,
        target: str,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record a single audit event."""
        event: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "actor": actor,
            "action": action,
            "target": target,
            "outcome": outcome,
        }
        if details:
            event["details"] = details

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit event: {e}")

    # ── Read ───────────────────────────────────────────────────────

    def _read_events(self) -> list[dict[str, Any]]:
        """Read all events from the JSONL file."""
        if not self.log_path.exists():
            return []
        events = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events

    def query_logs(
        self,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit logs with optional filters."""
        events = self._read_events()

        if actor:
            events = [e for e in events if e.get("actor") == actor]
        if action:
            events = [e for e in events if e.get("action") == action]

        return events[-limit:]

    def get_summary(self, hours: int = 24) -> dict[str, Any]:
        """Aggregated stats for the last N hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        events = self._read_events()

        recent = []
        for e in events:
            try:
                ts = datetime.fromisoformat(e["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if ts >= cutoff:
                    recent.append(e)
            except (KeyError, ValueError):
                continue

        by_action: dict[str, int] = defaultdict(int)
        by_outcome: dict[str, int] = defaultdict(int)
        by_actor: dict[str, int] = defaultdict(int)
        failures: list[dict[str, Any]] = []

        for e in recent:
            by_action[e.get("action", "unknown")] += 1
            by_outcome[e.get("outcome", "unknown")] += 1
            by_actor[e.get("actor", "unknown")] += 1
            if e.get("outcome") == "failure":
                failures.append(e)

        return {
            "period_hours": hours,
            "total_events": len(recent),
            "by_action": dict(by_action),
            "by_outcome": dict(by_outcome),
            "by_actor": dict(by_actor),
            "failures": failures[-10:],
        }


# Module-level singleton
audit = AuditLogger()
