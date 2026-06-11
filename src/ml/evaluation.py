"""ML Evaluation Pipeline."""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from src.config import settings


@dataclass
class EvaluationResult:
    query: str
    answer: str
    expected: str
    model_used: str
    latency_ms: int
    tokens_input: int
    tokens_output: int
    cost_usd: float
    relevance_score: float  # 0-1
    accuracy_score: float  # 0-1
    completeness_score: float  # 0-1
    overall_score: float  # 0-1
    tools_used: list[str]
    hallucination_detected: bool
    feedback: Optional[str] = None


class MLEvaluator:
    def __init__(self):
        self.results: list[EvaluationResult] = []

    def evaluate_relevance(self, query: str, answer: str) -> float:
        """Score how relevant the answer is to the query."""
        query_keywords = set(query.lower().split())
        answer_words = set(answer.lower().split())

        overlap = len(query_keywords.intersection(answer_words))
        total = len(query_keywords)

        if total == 0:
            return 0.0

        return min(overlap / total, 1.0)

    def evaluate_accuracy(self, answer: str, expected: str) -> float:
        """Score factual accuracy against expected answer."""
        # Simple keyword matching for demo
        answer_lower = answer.lower()
        expected_lower = expected.lower()

        # Extract numbers from both
        import re
        answer_numbers = set(re.findall(r'\d+\.?\d*', answer_lower))
        expected_numbers = set(re.findall(r'\d+\.?\d*', expected_lower))

        if not expected_numbers:
            return 1.0 if answer_lower == expected_lower else 0.5

        overlap = len(answer_numbers.intersection(expected_numbers))
        return overlap / len(expected_numbers) if expected_numbers else 0.0

    def evaluate_completeness(self, answer: str, expected: str) -> float:
        """Score how complete the answer is."""
        # Check if key concepts are covered
        expected_concepts = set(expected.lower().split())
        answer_concepts = set(answer.lower().split())

        coverage = len(expected_concepts.intersection(answer_concepts))
        total = len(expected_concepts)

        return coverage / total if total > 0 else 0.0

    def detect_hallucination(self, answer: str, context: str) -> bool:
        """Detect potential hallucinations."""
        # Simple heuristic: check if answer contains numbers not in context
        import re

        answer_numbers = set(re.findall(r'\d+\.?\d+', answer))
        context_numbers = set(re.findall(r'\d+\.?\d+', context))

        # If answer has many numbers not in context, possible hallucination
        if answer_numbers and context_numbers:
            new_numbers = answer_numbers - context_numbers
            return len(new_numbers) > len(answer_numbers) * 0.5

        return False

    def run_evaluation(
        self,
        queries: list[dict],
        orchestrator,
    ) -> list[EvaluationResult]:
        """Run full evaluation on a set of queries."""
        results = []

        for query_data in queries:
            query = query_data["question"]
            expected = query_data.get("expected_answer", "")

            # Run query
            import time
            start = time.time()
            result = orchestrator.run(query)
            latency_ms = int((time.time() - start) * 1000)

            # Calculate scores
            relevance = self.evaluate_relevance(query, result.answer)
            accuracy = self.evaluate_accuracy(result.answer, expected)
            completeness = self.evaluate_completeness(result.answer, expected)
            overall = (relevance + accuracy + completeness) / 3

            eval_result = EvaluationResult(
                query=query,
                answer=result.answer,
                expected=expected,
                model_used=result.model_used,
                latency_ms=latency_ms,
                tokens_input=0,
                tokens_output=0,
                cost_usd=result.total_cost_usd,
                relevance_score=relevance,
                accuracy_score=accuracy,
                completeness_score=completeness,
                overall_score=overall,
                tools_used=result.tools_used,
                hallucination_detected=self.detect_hallucination(
                    result.answer, ""
                ),
            )

            results.append(eval_result)
            self.results.append(eval_result)

        return results

    def get_metrics(self) -> dict:
        """Get aggregate metrics."""
        if not self.results:
            return {}

        return {
            "total_queries": len(self.results),
            "avg_relevance": sum(r.relevance_score for r in self.results) / len(self.results),
            "avg_accuracy": sum(r.accuracy_score for r in self.results) / len(self.results),
            "avg_completeness": sum(r.completeness_score for r in self.results) / len(self.results),
            "avg_overall": sum(r.overall_score for r in self.results) / len(self.results),
            "avg_latency_ms": sum(r.latency_ms for r in self.results) / len(self.results),
            "total_cost_usd": sum(r.cost_usd for r in self.results),
            "hallucination_rate": sum(1 for r in self.results if r.hallucination_detected) / len(self.results),
        }

    def save_results(self, path: Optional[Path] = None):
        """Save evaluation results to JSON."""
        path = path or settings.eval_dir / "evaluation_results.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump([asdict(r) for r in self.results], f, indent=2)
