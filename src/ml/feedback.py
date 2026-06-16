"""Feedback storage and aggregation for query responses."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from src.config import settings

logger = logging.getLogger(__name__)

FEEDBACK_DIR = settings.data_dir / "feedback"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def store_feedback(
    query: str,
    answer: str,
    rating: int,
    comment: str | None = None,
) -> dict:
    """Store feedback entry."""
    entry = {
        "id": f"fb_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "query": query,
        "answer": answer[:500],  # truncate for storage
        "rating": rating,
        "comment": comment,
        "timestamp": datetime.now().isoformat(),
    }

    # Append to daily file
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = FEEDBACK_DIR / f"{today}.jsonl"

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info(f"Stored feedback: {entry['id']} rating={rating}")
    return entry


def get_feedback_stats() -> dict:
    """Aggregate feedback stats across all days."""
    total = 0
    positive = 0
    negative = 0
    neutral = 0

    for file_path in FEEDBACK_DIR.glob("*.jsonl"):
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    total += 1
                    r = entry.get("rating", 0)
                    if r > 0:
                        positive += 1
                    elif r < 0:
                        negative += 1
                    else:
                        neutral += 1
                except json.JSONDecodeError:
                    continue

    avg = (positive - negative) / total if total > 0 else 0.0

    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "avg_score": round(avg, 3),
    }


def get_recent_feedback(limit: int = 20) -> list[dict]:
    """Get recent feedback entries."""
    entries = []

    for file_path in sorted(FEEDBACK_DIR.glob("*.jsonl"), reverse=True):
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        if len(entries) >= limit:
            break

    return entries[:limit]
