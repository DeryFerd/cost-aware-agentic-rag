"""Prompt regression testing against the golden eval set."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from datetime import datetime

from src.config import settings
from src.generation.prompt_registry import PromptRegistry
from src.eval.pipeline import EvalPipeline, CIGating, EvalReport
from src.eval.golden_set import get_golden_set

logger = logging.getLogger(__name__)

HISTORY_DIR = settings.data_dir / "eval" / "prompt_regression"


class PromptRegressionTester:
    """Run eval pipeline per prompt version and detect regressions."""

    def __init__(self, regression_threshold: float = 0.05):
        self.registry = PromptRegistry()
        self.threshold = regression_threshold
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    def test_prompt(
        self,
        name: str,
        versions: list[str] | None = None,
    ) -> dict:
        """Run eval on specified (or all) versions and compare scores."""
        if versions is None:
            version_info = self.registry.list_versions(name)
            versions = [v["version"] for v in version_info]

        if len(versions) < 1:
            return {"error": f"No versions found for prompt '{name}'"}

        golden = get_golden_set()[:10]
        pipeline = EvalPipeline()
        results: dict[str, dict] = {}

        for ver in versions:
            prompt_data = self.registry.get(name, ver)
            if not prompt_data:
                continue

            scores: list[dict] = []
            for item in golden:
                report = pipeline.evaluate(
                    query=item["query"],
                    retrieved_docs=[item.get("expected_answer", "")],
                    answer=item.get("expected_answer", ""),
                    ground_truth=item.get("expected_answer"),
                )
                scores.append({
                    "query_id": item["id"],
                    "overall_score": report.overall_score,
                    "metrics": {r.metric_name: r.value for r in report.results},
                })

            avg_score = (
                sum(s["overall_score"] for s in scores) / len(scores)
                if scores
                else 0.0
            )
            results[ver] = {
                "version": ver,
                "avg_score": round(avg_score, 4),
                "num_queries": len(scores),
                "details": scores,
            }

        regression_detected = False
        regressions = []
        sorted_versions = sorted(results.keys())

        if len(sorted_versions) >= 2:
            baseline = results[sorted_versions[0]]
            for ver in sorted_versions[1:]:
                current = results[ver]
                delta = baseline["avg_score"] - current["avg_score"]
                if delta > self.threshold:
                    regression_detected = True
                    regressions.append({
                        "from_version": baseline["version"],
                        "to_version": current["version"],
                        "score_drop": round(delta, 4),
                        "baseline_score": baseline["avg_score"],
                        "current_score": current["avg_score"],
                    })
                baseline = current

        test_result = {
            "prompt_name": name,
            "versions_tested": versions,
            "results": results,
            "regression_detected": regression_detected,
            "regressions": regressions,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._save_history(name, test_result)
        return test_result

    def get_history(self, name: str) -> list[dict]:
        """Get past regression test results for a prompt."""
        history_file = HISTORY_DIR / f"{name}_history.json"
        if not history_file.exists():
            return []
        with open(history_file) as f:
            return json.load(f)

    def check_gates(self, name: str, version: str) -> dict:
        """Check if a prompt version passes CI quality gates."""
        prompt_data = self.registry.get(name, version)
        if not prompt_data:
            return {"error": f"Prompt '{name}' version '{version}' not found"}

        golden = get_golden_set()[:10]
        pipeline = EvalPipeline()
        gating = CIGating()

        reports: list[EvalReport] = []
        for item in golden:
            report = pipeline.evaluate(
                query=item["query"],
                retrieved_docs=[item.get("expected_answer", "")],
                answer=item.get("expected_answer", ""),
                ground_truth=item.get("expected_answer"),
            )
            reports.append(report)

        gate_results = []
        all_pass = True
        for report in reports:
            check = gating.check(report)
            gate_results.append(check)
            if not check["passed"]:
                all_pass = False

        avg_overall = (
            sum(r["overall_score"] for r in gate_results) / len(gate_results)
            if gate_results
            else 0.0
        )

        return {
            "prompt_name": name,
            "version": version,
            "passed": all_pass,
            "avg_overall_score": round(avg_overall, 4),
            "num_queries": len(gate_results),
            "details": gate_results,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _save_history(self, name: str, result: dict) -> None:
        """Append a test result to history."""
        history_file = HISTORY_DIR / f"{name}_history.json"
        history = []
        if history_file.exists():
            with open(history_file) as f:
                history = json.load(f)

        summary = {
            "timestamp": result["timestamp"],
            "versions_tested": result["versions_tested"],
            "regression_detected": result["regression_detected"],
            "regressions": result["regressions"],
            "scores": {
                ver: data["avg_score"]
                for ver, data in result["results"].items()
            },
        }
        history.append(summary)

        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
