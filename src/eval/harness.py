"""Unified eval harness for the cost-aware agentic RAG system.

Runs the golden set through the orchestrator, evaluates with the LLM judge,
tracks retrieval metrics, computes cost/latency, and produces a structured report.

Usage:
    python -m src.eval.harness
    python -m src.eval.harness --baseline data/eval/harness_results.json
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

# ── Data Structures ──────────────────────────────────────────────


@dataclass
class EvalEntry:
    """Result of evaluating a single golden-set entry."""
    id: str
    query: str
    expected_answer: str
    category: str
    difficulty: str
    answer: str = ""
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    overall_score: float = 0.0
    failure_bucket: str = "correct"
    error: str = ""
    citations: list[str] = field(default_factory=list)
    chunks_used: int = 0
    tools_used: list[str] = field(default_factory=list)
    model_used: str = ""


@dataclass
class HarnessReport:
    """Full evaluation harness report."""
    timestamp: str = ""
    total_entries: int = 0
    overall_score: float = 0.0
    faithfulness_avg: float = 0.0
    answer_relevancy_avg: float = 0.0
    context_precision_avg: float = 0.0
    context_recall_avg: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    cost_per_answer_usd: float = 0.0
    total_cost_usd: float = 0.0
    failure_buckets: dict[str, int] = field(default_factory=dict)
    category_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    entries: list[dict[str, Any]] = field(default_factory=list)
    baseline_comparison: dict[str, Any] | None = None
    ci_gates: dict[str, Any] = field(default_factory=dict)


# ── Golden Set Loader ───────────────────────────────────────────


def load_golden_set(path: str | Path | None = None) -> list[dict]:
    """Load golden set from JSON file, falling back to the Python module."""
    path = settings.eval_dir / "golden_set.json" if path is None else Path(path)

    if path.exists():
        with open(path) as f:
            return json.load(f)

    # Fallback to the Python golden set
    from src.eval.golden_set import get_golden_set
    return get_golden_set()


# ── LLM Judge Wrapper ──────────────────────────────────────────


def _judge_entry(
    entry: EvalEntry,
    query: str,
    answer: str,
    contexts: list[str],
    ground_truth: str,
) -> EvalEntry:
    """Evaluate a single entry with the LLM judge, returning structured scores."""
    try:
        from src.eval.llm_judge import LLMJudge

        judge = LLMJudge()
        result = judge.evaluate(
            question=query,
            answer=answer,
            contexts=contexts,
            ground_truth=ground_truth,
        )
        entry.faithfulness = result.faithfulness
        entry.answer_relevancy = result.answer_relevancy
        entry.context_precision = result.context_precision
        entry.context_recall = result.context_recall
        entry.overall_score = (
            result.faithfulness * 0.3
            + result.answer_relevancy * 0.3
            + result.context_precision * 0.2
            + result.context_recall * 0.2
        )
    except Exception as e:
        logger.warning(f"LLM judge failed for {entry.id}: {e}")
        # Fallback: heuristic scoring
        _heuristic_score(entry, answer, contexts, ground_truth)

    return entry


def _heuristic_score(
    entry: EvalEntry,
    answer: str,
    contexts: list[str],
    ground_truth: str,
) -> None:
    """Fallback heuristic scoring when LLM judge is unavailable."""
    answer_lower = answer.lower()
    gt_lower = ground_truth.lower()

    # Faithfulness: bigram overlap with ground truth
    answer_tokens = answer_lower.split()
    gt_tokens = gt_lower.split()
    answer_bigrams = set()
    gt_bigrams = set()
    for i in range(len(answer_tokens) - 1):
        answer_bigrams.add((answer_tokens[i], answer_tokens[i + 1]))
    for i in range(len(gt_tokens) - 1):
        gt_bigrams.add((gt_tokens[i], gt_tokens[i + 1]))

    if gt_bigrams:
        entry.faithfulness = len(answer_bigrams & gt_bigrams) / len(gt_bigrams)
    else:
        entry.faithfulness = 0.5

    # Relevancy: token overlap with query
    entry.answer_relevancy = 0.5  # neutral without query context here

    # Context precision: keyword overlap
    if contexts:
        ctx_text = " ".join(contexts).lower()
        q_words = set(entry.query.lower().split())
        ctx_words = set(ctx_text.split())
        entry.context_precision = len(q_words & ctx_words) / len(q_words) if q_words else 0.5
    else:
        entry.context_precision = 0.0

    # Context recall: ground truth coverage by contexts
    if contexts:
        ctx_text = " ".join(contexts).lower()
        ctx_words = set(ctx_text.split())
        gt_set = set(gt_lower.split())
        entry.context_recall = len(gt_set & ctx_words) / len(gt_set) if gt_set else 0.0
    else:
        entry.context_recall = 0.0

    entry.overall_score = (
        entry.faithfulness * 0.3
        + entry.answer_relevancy * 0.3
        + entry.context_precision * 0.2
        + entry.context_recall * 0.2
    )


# ── Failure Bucketing ──────────────────────────────────────────


def _classify_failure(entry: EvalEntry) -> str:
    """Classify an entry into a failure bucket."""
    if entry.error:
        if "timeout" in entry.error.lower():
            return "timeout"
        return "wrong_answer"

    if not entry.answer or entry.answer.strip() == "":
        return "no_answer"

    if entry.overall_score >= 0.7:
        return "correct"
    elif entry.overall_score >= 0.4:
        return "partial"
    else:
        return "wrong_answer"


# ── Baseline Comparison ─────────────────────────────────────────


def _compare_to_baseline(
    current: HarnessReport,
    baseline_path: str | Path,
) -> dict[str, Any]:
    """Compare current results to a baseline report."""
    baseline_path = Path(baseline_path)
    if not baseline_path.exists():
        return {"error": f"Baseline file not found: {baseline_path}"}

    with open(baseline_path) as f:
        baseline_data = json.load(f)

    baseline = HarnessReport(**{
        k: v for k, v in baseline_data.items()
        if k in HarnessReport.__dataclass_fields__
    })

    comparison: dict[str, Any] = {
        "baseline_timestamp": baseline.timestamp,
        "overall_score_delta": round(current.overall_score - baseline.overall_score, 4),
        "faithfulness_delta": round(current.faithfulness_avg - baseline.faithfulness_avg, 4),
        "answer_relevancy_delta": round(current.answer_relevancy_avg - baseline.answer_relevancy_avg, 4),
        "context_precision_delta": round(current.context_precision_avg - baseline.context_precision_avg, 4),
        "context_recall_delta": round(current.context_recall_avg - baseline.context_recall_avg, 4),
        "latency_p50_delta_ms": round(current.latency_p50_ms - baseline.latency_p50_ms, 2),
        "cost_per_answer_delta_usd": round(current.cost_per_answer_usd - baseline.cost_per_answer_usd, 6),
        "regression_detected": False,
        "regressions": [],
    }

    # Check for regressions > 10%
    regression_threshold = 0.10
    for metric in ["overall_score", "faithfulness_avg", "answer_relevancy_avg", "context_precision_avg", "context_recall_avg"]:
        current_val = getattr(current, metric, 0)
        baseline_val = getattr(baseline, metric, 0)
        if baseline_val > 0:
            delta_pct = (baseline_val - current_val) / baseline_val
            if delta_pct > regression_threshold:
                comparison["regression_detected"] = True
                comparison["regressions"].append({
                    "metric": metric,
                    "baseline": baseline_val,
                    "current": current_val,
                    "regression_pct": round(delta_pct * 100, 2),
                })

    return comparison


# ── CI Gate Checking ────────────────────────────────────────────


def _check_ci_gates(report: HarnessReport) -> dict[str, Any]:
    """Check if results pass CI quality gates."""
    gates = {
        "overall_score": {"threshold": 0.7, "passed": False},
        "faithfulness": {"threshold": 0.5, "passed": False},
        "no_major_regression": {"threshold": 0.10, "passed": True},
    }

    gates["overall_score"]["passed"] = report.overall_score >= 0.7
    gates["overall_score"]["actual"] = report.overall_score

    gates["faithfulness"]["passed"] = report.faithfulness_avg >= 0.5
    gates["faithfulness"]["actual"] = report.faithfulness_avg

    if report.baseline_comparison and report.baseline_comparison.get("regression_detected"):
        gates["no_major_regression"]["passed"] = False
        gates["no_major_regression"]["regressions"] = report.baseline_comparison.get("regressions", [])

    all_passed = all(g["passed"] for g in gates.values())
    return {"all_passed": all_passed, "gates": gates}


# ── Report Printing ─────────────────────────────────────────────


def _print_summary(report: HarnessReport) -> None:
    """Print a formatted summary table to stdout."""
    print("\n" + "=" * 72)
    print("  EVAL HARNESS REPORT")
    print("=" * 72)
    print(f"  Timestamp:          {report.timestamp}")
    print(f"  Total entries:      {report.total_entries}")
    print("-" * 72)

    print(f"  Overall score:      {report.overall_score:.4f}")
    print(f"  Faithfulness avg:   {report.faithfulness_avg:.4f}")
    print(f"  Answer relevancy:   {report.answer_relevancy_avg:.4f}")
    print(f"  Context precision:  {report.context_precision_avg:.4f}")
    print(f"  Context recall:     {report.context_recall_avg:.4f}")
    print("-" * 72)

    print(f"  Latency p50:        {report.latency_p50_ms:.0f} ms")
    print(f"  Latency p95:        {report.latency_p95_ms:.0f} ms")
    print(f"  Cost per answer:    ${report.cost_per_answer_usd:.6f}")
    print(f"  Total cost:         ${report.total_cost_usd:.6f}")
    print("-" * 72)

    print("  Failure Buckets:")
    for bucket, count in sorted(report.failure_buckets.items()):
        print(f"    {bucket:<25} {count}")
    print("-" * 72)

    print("  Category Breakdown:")
    for cat, data in sorted(report.category_breakdown.items()):
        print(f"    {cat:<20} score={data['avg_score']:.3f}  n={data['count']}")
    print("-" * 72)

    if report.baseline_comparison and "error" not in report.baseline_comparison:
        bc = report.baseline_comparison
        print("  Baseline Comparison:")
        print(f"    Overall delta:     {bc['overall_score_delta']:+.4f}")
        print(f"    Faith delta:       {bc['faithfulness_delta']:+.4f}")
        print(f"    Regression:        {'YES' if bc['regression_detected'] else 'NO'}")
        if bc.get("regressions"):
            for reg in bc["regressions"]:
                print(f"      - {reg['metric']}: {reg['regression_pct']:.1f}% regression")
        print("-" * 72)

    ci = report.ci_gates
    if ci:
        print("  CI Gates:")
        for gate_name, gate_data in ci.get("gates", {}).items():
            status = "PASS" if gate_data["passed"] else "FAIL"
            actual = gate_data.get("actual", "n/a")
            threshold = gate_data["threshold"]
            print(f"    {gate_name:<25} {status}  (actual={actual}, threshold={threshold})")
        print(f"    {'all_passed':<25} {'PASS' if ci['all_passed'] else 'FAIL'}")
    print("=" * 72 + "\n")


# ── Main Harness ────────────────────────────────────────────────


def run_harness(
    golden_set_path: str | Path | None = None,
    baseline_path: str | Path | None = None,
    timeout_seconds: float = 120.0,
) -> HarnessReport:
    """Run the full evaluation harness.

    Args:
        golden_set_path: Path to the golden set JSON.
        baseline_path: Optional path to a previous results file for comparison.
        timeout_seconds: Max seconds per query before marking as timeout.

    Returns:
        HarnessReport with all results.
    """
    from datetime import datetime

    golden_set = load_golden_set(golden_set_path)
    logger.info(f"Loaded {len(golden_set)} golden entries")

    # Lazy-import orchestrator
    from src.agents.graph import LangGraphOrchestrator

    orchestrator = LangGraphOrchestrator()

    entries: list[EvalEntry] = []
    latencies: list[float] = []

    for i, item in enumerate(golden_set):
        entry = EvalEntry(
            id=item["id"],
            query=item["query"],
            expected_answer=item.get("expected_answer", ""),
            category=item.get("category", "unknown"),
            difficulty=item.get("difficulty", "unknown"),
        )

        logger.info(f"[{i + 1}/{len(golden_set)}] Evaluating: {item['query'][:60]}...")

        t0 = time.perf_counter()
        try:
            result = orchestrator.run(
                query=item["query"],
                thread_id=f"eval_{item['id']}",
            )
            entry.answer = result.get("answer", "")
            entry.cost_usd = result.get("total_cost_usd", 0.0)
            entry.citations = result.get("citations", [])
            entry.chunks_used = result.get("chunks_used", 0)
            entry.tools_used = result.get("tools_used", [])
            entry.model_used = result.get("model_used", "")
            entry.latency_ms = result.get("total_latency_ms", 0.0)
        except Exception as e:
            entry.error = str(e)
            logger.error(f"Query {item['id']} failed: {e}")

        # Enforce timeout
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if elapsed_ms > timeout_seconds * 1000:
            entry.error = f"Timeout after {timeout_seconds}s"
            entry.latency_ms = elapsed_ms
        elif not entry.latency_ms:
            entry.latency_ms = elapsed_ms

        latencies.append(entry.latency_ms)

        # LLM judge evaluation
        _judge_entry(
            entry,
            query=item["query"],
            answer=entry.answer,
            contexts=[],  # contexts are embedded in the answer from orchestrator
            ground_truth=item.get("expected_answer", ""),
        )

        # Classify failure bucket
        entry.failure_bucket = _classify_failure(entry)

        entries.append(entry)

    # ── Aggregate metrics ───────────────────────────────────────

    n = len(entries) if entries else 1
    latencies_sorted = sorted(latencies)

    report = HarnessReport(
        timestamp=datetime.now(UTC).isoformat(),
        total_entries=len(entries),
        overall_score=round(sum(e.overall_score for e in entries) / n, 4),
        faithfulness_avg=round(sum(e.faithfulness for e in entries) / n, 4),
        answer_relevancy_avg=round(sum(e.answer_relevancy for e in entries) / n, 4),
        context_precision_avg=round(sum(e.context_precision for e in entries) / n, 4),
        context_recall_avg=round(sum(e.context_recall for e in entries) / n, 4),
        latency_p50_ms=round(_percentile(latencies_sorted, 0.50), 2),
        latency_p95_ms=round(_percentile(latencies_sorted, 0.95), 2),
        cost_per_answer_usd=round(sum(e.cost_usd for e in entries) / n, 6),
        total_cost_usd=round(sum(e.cost_usd for e in entries), 6),
        failure_buckets=_bucket_counts(entries),
        category_breakdown=_category_breakdown(entries),
        entries=[asdict(e) for e in entries],
    )

    # Baseline comparison
    if baseline_path:
        report.baseline_comparison = _compare_to_baseline(report, baseline_path)

    # CI gates
    report.ci_gates = _check_ci_gates(report)

    return report


def _percentile(sorted_data: list[float], p: float) -> float:
    """Compute the p-th percentile from sorted data."""
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * p
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    d = k - f
    return sorted_data[f] + d * (sorted_data[c] - sorted_data[f])


def _bucket_counts(entries: list[EvalEntry]) -> dict[str, int]:
    """Count entries per failure bucket."""
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.failure_bucket] = counts.get(e.failure_bucket, 0) + 1
    return counts


def _category_breakdown(entries: list[EvalEntry]) -> dict[str, dict[str, Any]]:
    """Compute per-category average scores."""
    cats: dict[str, list[EvalEntry]] = {}
    for e in entries:
        cats.setdefault(e.category, []).append(e)

    breakdown: dict[str, dict[str, Any]] = {}
    for cat, cat_entries in cats.items():
        n = len(cat_entries)
        breakdown[cat] = {
            "count": n,
            "avg_score": round(sum(e.overall_score for e in cat_entries) / n, 4) if n else 0,
            "avg_faithfulness": round(sum(e.faithfulness for e in cat_entries) / n, 4) if n else 0,
            "avg_latency_ms": round(sum(e.latency_ms for e in cat_entries) / n, 2) if n else 0,
            "avg_cost_usd": round(sum(e.cost_usd for e in cat_entries) / n, 6) if n else 0,
        }
    return breakdown


# ── Save / CLI ──────────────────────────────────────────────────


def save_report(report: HarnessReport, output_path: str | Path | None = None) -> Path:
    """Save the harness report to JSON."""
    output_path = settings.eval_dir / "harness_results.json" if output_path is None else Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(asdict(report), f, indent=2)

    logger.info(f"Report saved to {output_path}")
    return output_path


def main() -> int:
    """CLI entry point for the eval harness."""
    import argparse

    parser = argparse.ArgumentParser(description="Cost-Aware Agentic RAG Eval Harness")
    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Path to baseline results JSON for regression comparison",
    )
    parser.add_argument(
        "--golden-set",
        type=str,
        default=None,
        help="Path to golden set JSON (default: data/eval/golden_set.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for results (default: data/eval/harness_results.json)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Timeout per query in seconds (default: 120)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    report = run_harness(
        golden_set_path=args.golden_set,
        baseline_path=args.baseline,
        timeout_seconds=args.timeout,
    )

    output_path = save_report(report, args.output)
    print(f"\nResults saved to: {output_path}")

    _print_summary(report)

    # Exit code: 1 if CI gates fail
    if not report.ci_gates.get("all_passed", False):
        print("CI GATES FAILED — exiting with code 1")
        return 1

    print("ALL CI GATES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
