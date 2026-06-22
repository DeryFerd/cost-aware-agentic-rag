"""Quick cost-quality report for CI regression gating.

Runs a small subset of the golden set, persists results to SQLite,
and compares against the latest baseline. Exits non-zero on regression.

Usage:
    python scripts/cost_quality_report.py --queries 5
    python scripts/cost_quality_report.py --queries 10 --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.agents.graph import LangGraphOrchestrator
from src.eval.db import complete_run, create_run, get_baseline, save_result
from src.eval.golden_set import get_golden_set

logger = logging.getLogger(__name__)

# Regression thresholds
SCORE_REGRESSION_THRESHOLD = 0.10  # 10% drop in overall score
LATENCY_REGRESSION_THRESHOLD = 1.5  # 50% increase in p50 latency
COST_REGRESSION_THRESHOLD = 2.0  # 100% increase in cost


def _classify_bucket(score: float, answer: str) -> str:
    if not answer or answer.strip() == "":
        return "no_answer"
    if score >= 0.7:
        return "correct"
    if score >= 0.4:
        return "partial"
    return "wrong"


def run_report(num_queries: int) -> dict:
    golden = get_golden_set()[:num_queries]
    orchestrator = LangGraphOrchestrator()

    run_id = create_run({"num_queries": num_queries, "source": "ci"})
    results = []

    for i, item in enumerate(golden):
        logger.info("[%d/%d] %s", i + 1, len(golden), item["query"][:60])
        t0 = time.perf_counter()
        try:
            resp = orchestrator.run(item["query"])
            answer = resp.get("answer", "")
            latency_ms = resp.get("total_latency_ms", (time.perf_counter() - t0) * 1000)
            cost_usd = resp.get("total_cost_usd", 0.0)
            model_used = resp.get("model_used", "")
        except Exception as e:
            logger.error("Query %s failed: %s", item["id"], e)
            answer = ""
            latency_ms = (time.perf_counter() - t0) * 1000
            cost_usd = 0.0
            model_used = "error"

        expected = item.get("expected_answer", "")
        score = 0.0
        if expected and answer:
            overlap = len(set(expected.lower().split()) & set(answer.lower().split()))
            denom = len(set(expected.lower().split()))
            score = overlap / denom if denom else 0.0

        bucket = _classify_bucket(score, answer)
        result = {
            "query_id": item["id"],
            "query": item["query"],
            "expected_answer": expected,
            "actual_answer": answer,
            "score": round(score, 4),
            "faithfulness": round(score, 4),
            "relevancy": round(score, 4),
            "latency_ms": round(latency_ms, 2),
            "cost_usd": round(cost_usd, 6),
            "model_used": model_used,
            "bucket": bucket,
        }
        results.append(result)
        save_result(run_id, result)

    scores = [r["score"] for r in results]
    latencies = [r["latency_ms"] for r in results]
    costs = [r["cost_usd"] for r in results]

    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50 = sorted_lat[n // 2] if n else 0
    p95 = sorted_lat[int(n * 0.95)] if n else 0

    summary = {
        "total_queries": len(results),
        "overall_score": round(statistics.mean(scores) if scores else 0, 4),
        "faithfulness": round(statistics.mean(scores) if scores else 0, 4),
        "relevancy": round(statistics.mean(scores) if scores else 0, 4),
        "latency_p50": round(p50, 2),
        "latency_p95": round(p95, 2),
        "total_cost": round(sum(costs), 6),
    }
    complete_run(run_id, summary)

    report = {
        "run_id": run_id,
        "summary": summary,
        "results": results,
    }

    # Compare to baseline
    baseline = get_baseline()
    if baseline and baseline.get("run_id") != run_id:
        regression = _check_regression(summary, baseline)
        report["baseline_comparison"] = regression
        if regression["regressed"]:
            logger.error("REGRESSION DETECTED: %s", json.dumps(regression, indent=2))
        else:
            logger.info("No regression detected vs baseline %s", baseline["run_id"])
    else:
        report["baseline_comparison"] = {"note": "No baseline available for comparison"}

    # Save JSON
    out_path = project_root / "data" / "eval" / "cost_quality_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Report saved to %s", out_path)

    return report


def _check_regression(current: dict, baseline: dict) -> dict:
    result = {"regressed": False, "details": []}

    base_score = baseline.get("overall_score") or 0
    cur_score = current.get("overall_score") or 0
    if base_score > 0 and (base_score - cur_score) / base_score > SCORE_REGRESSION_THRESHOLD:
        result["regressed"] = True
        result["details"].append(
            f"overall_score dropped {((base_score - cur_score) / base_score) * 100:.1f}% "
            f"(baseline={base_score:.4f}, current={cur_score:.4f})"
        )

    base_lat = baseline.get("latency_p50") or 1
    cur_lat = current.get("latency_p50") or 0
    if cur_lat > base_lat * LATENCY_REGRESSION_THRESHOLD:
        result["regressed"] = True
        result["details"].append(
            f"latency_p50 increased {cur_lat / base_lat:.1f}x "
            f"(baseline={base_lat:.0f}ms, current={cur_lat:.0f}ms)"
        )

    base_cost = baseline.get("total_cost") or 1e-9
    cur_cost = current.get("total_cost") or 0
    if cur_cost > base_cost * COST_REGRESSION_THRESHOLD:
        result["regressed"] = True
        result["details"].append(
            f"total_cost increased {cur_cost / base_cost:.1f}x "
            f"(baseline=${base_cost:.6f}, current=${cur_cost:.6f})"
        )

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Cost-quality regression report")
    parser.add_argument("--queries", type=int, default=5, help="Number of queries to run")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    report = run_report(args.queries)

    comparison = report.get("baseline_comparison", {})
    if comparison.get("regressed"):
        print("FAIL: Regression detected")
        for detail in comparison.get("details", []):
            print(f"  - {detail}")
        return 1

    print("PASS: No regression detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
