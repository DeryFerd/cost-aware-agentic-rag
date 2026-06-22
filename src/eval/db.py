"""SQLite persistence for eval runs and results."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "eval" / "eval_runs.db"


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT UNIQUE NOT NULL,
            timestamp TEXT NOT NULL,
            total_queries INTEGER,
            overall_score REAL,
            faithfulness REAL,
            relevancy REAL,
            latency_p50 REAL,
            latency_p95 REAL,
            total_cost REAL,
            config TEXT,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS eval_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            query_id TEXT,
            query TEXT,
            expected_answer TEXT,
            actual_answer TEXT,
            score REAL,
            faithfulness REAL,
            relevancy REAL,
            latency_ms REAL,
            cost_usd REAL,
            model_used TEXT,
            bucket TEXT,
            FOREIGN KEY (run_id) REFERENCES eval_runs(run_id)
        );
    """)


def create_run(config: dict | None = None) -> str:
    """Create a new eval run and return its run_id."""
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    timestamp = datetime.now(UTC).isoformat()
    config_json = json.dumps(config or {})

    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO eval_runs (run_id, timestamp, config, status) VALUES (?, ?, ?, ?)",
            (run_id, timestamp, config_json, "running"),
        )
        conn.commit()
        logger.info("Created eval run %s", run_id)
        return run_id
    finally:
        conn.close()


def save_result(run_id: str, result: dict) -> None:
    """Save a single query result for an eval run."""
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO eval_results
               (run_id, query_id, query, expected_answer, actual_answer,
                score, faithfulness, relevancy, latency_ms, cost_usd,
                model_used, bucket)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                result.get("query_id", ""),
                result.get("query", ""),
                result.get("expected_answer", ""),
                result.get("actual_answer", ""),
                result.get("score", 0.0),
                result.get("faithfulness", 0.0),
                result.get("relevancy", 0.0),
                result.get("latency_ms", 0.0),
                result.get("cost_usd", 0.0),
                result.get("model_used", ""),
                result.get("bucket", "correct"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def complete_run(run_id: str, summary: dict) -> None:
    """Mark a run as completed and store aggregate summary metrics."""
    conn = _connect()
    try:
        conn.execute(
            """UPDATE eval_runs
               SET status = 'completed',
                   total_queries = ?,
                   overall_score = ?,
                   faithfulness = ?,
                   relevancy = ?,
                   latency_p50 = ?,
                   latency_p95 = ?,
                   total_cost = ?
               WHERE run_id = ?""",
            (
                summary.get("total_queries", 0),
                summary.get("overall_score", 0.0),
                summary.get("faithfulness", 0.0),
                summary.get("relevancy", 0.0),
                summary.get("latency_p50", 0.0),
                summary.get("latency_p95", 0.0),
                summary.get("total_cost", 0.0),
                run_id,
            ),
        )
        conn.commit()
        logger.info("Completed eval run %s", run_id)
    finally:
        conn.close()


def fail_run(run_id: str) -> None:
    """Mark a run as failed."""
    conn = _connect()
    try:
        conn.execute("UPDATE eval_runs SET status = 'failed' WHERE run_id = ?", (run_id,))
        conn.commit()
    finally:
        conn.close()


def get_runs(limit: int = 20) -> list[dict]:
    """Return the most recent eval runs."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM eval_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_run(run_id: str) -> dict | None:
    """Return a single run and its individual results."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM eval_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None

        run_data = dict(row)
        results = conn.execute(
            "SELECT * FROM eval_results WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        run_data["results"] = [dict(r) for r in results]
        return run_data
    finally:
        conn.close()


def get_baseline() -> dict | None:
    """Return the latest completed eval run as the baseline."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM eval_runs WHERE status = 'completed' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None

        run_data = dict(row)
        results = conn.execute(
            "SELECT * FROM eval_results WHERE run_id = ? ORDER BY id", (run_data["run_id"],)
        ).fetchall()
        run_data["results"] = [dict(r) for r in results]
        return run_data
    finally:
        conn.close()
