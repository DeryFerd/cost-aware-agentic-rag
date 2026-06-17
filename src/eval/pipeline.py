"""Evaluation pipeline for RAG system."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    """Single evaluation result."""
    metric_name: str
    value: float
    details: dict = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class EvalReport:
    """Complete evaluation report."""
    query: str
    results: list[EvalResult]
    overall_score: float
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)


class EvalPipeline:
    """End-to-end evaluation pipeline for RAG system."""

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self.metrics: dict[str, callable] = {}
        self._register_default_metrics()

    def _register_default_metrics(self):
        """Register default evaluation metrics."""
        self.metrics["retrieval_precision"] = self._retrieval_precision
        self.metrics["retrieval_recall"] = self._retrieval_recall
        self.metrics["context_relevance"] = self._context_relevance
        self.metrics["answer_faithfulness"] = self._answer_faithfulness
        self.metrics["answer_relevance"] = self._answer_relevance
        self.metrics["latency"] = self._latency_metric

    def evaluate(
        self,
        query: str,
        retrieved_docs: list[str],
        answer: str,
        ground_truth: str | None = None,
        expected_docs: list[str] | None = None,
    ) -> EvalReport:
        """Run full evaluation pipeline.

        Args:
            query: User query
            retrieved_docs: List of retrieved document texts
            answer: Generated answer
            ground_truth: Expected answer (if available)
            expected_docs: Expected relevant documents (if available)

        Returns:
            EvalReport with all metrics
        """
        results = []

        # Run each metric
        for name, metric_fn in self.metrics.items():
            try:
                start_time = time.time()
                value = metric_fn(
                    query=query,
                    retrieved_docs=retrieved_docs,
                    answer=answer,
                    ground_truth=ground_truth,
                    expected_docs=expected_docs,
                )
                elapsed = time.time() - start_time

                results.append(EvalResult(
                    metric_name=name,
                    value=value,
                    details={"computation_time": elapsed},
                    timestamp=time.time(),
                ))
            except Exception as e:
                logger.warning(f"Metric {name} failed: {e}")
                results.append(EvalResult(
                    metric_name=name,
                    value=0.0,
                    details={"error": str(e)},
                    timestamp=time.time(),
                ))

        # Calculate overall score
        scores = [r.value for r in results if r.metric_name != "latency"]
        overall = sum(scores) / len(scores) if scores else 0.0

        return EvalReport(
            query=query,
            results=results,
            overall_score=overall,
            timestamp=time.time(),
            metadata={"num_docs": len(retrieved_docs)},
        )

    def _retrieval_precision(
        self,
        query: str,
        retrieved_docs: list[str],
        answer: str,
        ground_truth: str | None = None,
        expected_docs: list[str] | None = None,
    ) -> float:
        """Fraction of retrieved docs that are relevant."""
        if not expected_docs or not retrieved_docs:
            return 0.5  # Neutral score when no ground truth

        relevant_count = 0
        for doc in retrieved_docs:
            for expected in expected_docs:
                if self._text_similarity(doc, expected) > 0.3:
                    relevant_count += 1
                    break

        return relevant_count / len(retrieved_docs)

    def _retrieval_recall(
        self,
        query: str,
        retrieved_docs: list[str],
        answer: str,
        ground_truth: str | None = None,
        expected_docs: list[str] | None = None,
    ) -> float:
        """Fraction of relevant docs that were retrieved."""
        if not expected_docs:
            return 0.5

        retrieved_count = 0
        for expected in expected_docs:
            for doc in retrieved_docs:
                if self._text_similarity(doc, expected) > 0.3:
                    retrieved_count += 1
                    break

        return retrieved_count / len(expected_docs)

    def _context_relevance(
        self,
        query: str,
        retrieved_docs: list[str],
        answer: str,
        ground_truth: str | None = None,
        expected_docs: list[str] | None = None,
    ) -> float:
        """How relevant are retrieved docs to the query."""
        if not retrieved_docs:
            return 0.0

        # Simple keyword overlap
        query_words = set(query.lower().split())
        total_score = 0.0

        for doc in retrieved_docs:
            doc_words = set(doc.lower().split())
            overlap = len(query_words & doc_words)
            total_score += overlap / len(query_words) if query_words else 0

        return min(1.0, total_score / len(retrieved_docs))

    def _answer_faithfulness(
        self,
        query: str,
        retrieved_docs: list[str],
        answer: str,
        ground_truth: str | None = None,
        expected_docs: list[str] | None = None,
    ) -> float:
        """Does the answer stay faithful to retrieved context."""
        if not retrieved_docs or not answer:
            return 0.5

        # Check if answer contains claims not in context
        answer_words = set(answer.lower().split())
        context_words = set()
        for doc in retrieved_docs:
            context_words.update(doc.lower().split())

        # Words in answer not in context (potential hallucination)
        unsupported = answer_words - context_words
        faithfulness = 1.0 - (len(unsupported) / len(answer_words) if answer_words else 0)

        return max(0.0, faithfulness)

    def _answer_relevance(
        self,
        query: str,
        retrieved_docs: list[str],
        answer: str,
        ground_truth: str | None = None,
        expected_docs: list[str] | None = None,
    ) -> float:
        """Is the answer relevant to the query."""
        if not answer:
            return 0.0

        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())

        overlap = len(query_words & answer_words)
        return overlap / len(query_words) if query_words else 0.5

    def _latency_metric(
        self,
        query: str,
        retrieved_docs: list[str],
        answer: str,
        ground_truth: str | None = None,
        expected_docs: list[str] | None = None,
    ) -> float:
        """Latency metric (inverted: lower is better)."""
        # This is handled externally, return neutral
        return 1.0

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple word overlap similarity."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union) if union else 0.0

    def save_report(self, report: EvalReport, path: str | Path | None = None):
        """Save evaluation report to file."""
        save_path = Path(path) if path else self.storage_path
        if not save_path:
            raise ValueError("No storage path specified")

        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "query": report.query,
            "overall_score": report.overall_score,
            "timestamp": report.timestamp,
            "metadata": report.metadata,
            "results": [
                {
                    "metric": r.metric_name,
                    "value": r.value,
                    "details": r.details,
                }
                for r in report.results
            ],
        }

        with open(save_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Evaluation report saved to {save_path}")


class CIGating:
    """CI/CD gating for RAG quality."""

    def __init__(self, thresholds: dict[str, float] | None = None):
        self.thresholds = thresholds or {
            "overall_score": 0.6,
            "retrieval_precision": 0.5,
            "retrieval_recall": 0.5,
            "answer_faithfulness": 0.6,
            "answer_relevance": 0.5,
        }

    def check(self, report: EvalReport) -> dict:
        """Check if evaluation passes CI gates.

        Args:
            report: EvalReport to check

        Returns:
            Dict with pass/fail and details
        """
        results = {}
        all_pass = True

        for result in report.results:
            threshold = self.thresholds.get(result.metric_name)
            if threshold is not None:
                passed = result.value >= threshold
                results[result.metric_name] = {
                    "value": result.value,
                    "threshold": threshold,
                    "passed": passed,
                }
                if not passed:
                    all_pass = False

        return {
            "passed": all_pass,
            "results": results,
            "overall_score": report.overall_score,
        }


class EvalStorage:
    """Store and retrieve evaluation history."""

    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save(self, report: EvalReport):
        """Save evaluation report."""
        filename = f"eval_{int(report.timestamp * 1000)}.json"
        filepath = self.storage_path / filename

        data = {
            "query": report.query,
            "overall_score": report.overall_score,
            "timestamp": report.timestamp,
            "results": [
                {"metric": r.metric_name, "value": r.value}
                for r in report.results
            ],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def get_history(self, limit: int = 100) -> list[dict]:
        """Get recent evaluation history."""
        files = sorted(self.storage_path.glob("eval_*.json"), reverse=True)[:limit]

        results = []
        for f in files:
            with open(f) as fp:
                results.append(json.load(fp))

        return results

    def get_average_scores(self, window: int = 10) -> dict:
        """Get average scores over recent evaluations."""
        history = self.get_history(limit=window)
        if not history:
            return {}

        metric_totals: dict[str, list[float]] = {}
        for entry in history:
            for result in entry.get("results", []):
                metric = result["metric"]
                if metric not in metric_totals:
                    metric_totals[metric] = []
                metric_totals[metric].append(result["value"])

        return {
            metric: sum(values) / len(values)
            for metric, values in metric_totals.items()
        }
