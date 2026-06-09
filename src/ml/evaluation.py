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
                tokens_input=result.tokens_input,
                tokens_output=result.tokens_output,
                cost_usd=result.cost_usd,
                relevance_score=relevance,
                accuracy_score=accuracy,
                completeness_score=completeness,
                overall_score=overall,
                tools_used=result.tools_used,
                hallucination_detected=self.detect_hallucination(
                    result.answer, str(result.context_data)
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


class CostOptimizer:
    """Optimize model selection based on query complexity."""

    SIMPLE_MODEL = "gemma3:4b"
    COMPLEX_MODEL = "gemma3:27b"

    # Cost per 1M tokens (approximate)
    COSTS = {
        "gemma3:4b": 0.0,
        "gemma3:27b": 0.0,
    }

    def classify_complexity(self, query: str) -> str:
        """Classify query as simple or complex."""
        query_lower = query.lower()

        # Simple patterns
        simple_patterns = [
            "what is",
            "how many",
            "what was",
            "when did",
            "who is",
        ]

        # Complex patterns
        complex_patterns = [
            "compare",
            "analyze",
            "explain why",
            "what are the implications",
            "summarize",
            "contrast",
            "evaluate",
            "assess",
        ]

        # Check for complex patterns first
        for pattern in complex_patterns:
            if pattern in query_lower:
                return "complex"

        # Check for simple patterns
        for pattern in simple_patterns:
            if pattern in query_lower:
                return "simple"

        # Default to simple
        return "simple"

    def select_model(self, query: str, budget: float = 0.05) -> str:
        """Select model based on query complexity and budget."""
        complexity = self.classify_complexity(query)

        if complexity == "complex":
            return self.COMPLEX_MODEL
        else:
            return self.SIMPLE_MODEL

    def predict_cost(self, query: str, model: str) -> float:
        """Predict cost for a query."""
        # Rough token estimation
        input_tokens = len(query.split()) * 2
        output_tokens = 500  # Average response length

        cost_per_token = self.COSTS.get(model, 0.0) / 1_000_000
        return (input_tokens + output_tokens) * cost_per_token


class RetrievalOptimizer:
    """Optimize retrieval performance."""

    def expand_query(self, query: str) -> str:
        """Expand query with HyDE (Hypothetical Document Embeddings)."""
        # Simple expansion for demo
        expanded = query

        # Add synonyms
        synonyms = {
            "revenue": "revenue sales income",
            "profit": "profit earnings net income",
            "employees": "employees workforce staff",
        }

        for word, expansion in synonyms.items():
            if word in query.lower():
                expanded = f"{query} {expansion}"
                break

        return expanded

    def rerank_results(self, query: str, results: list[dict]) -> list[dict]:
        """Re-rank results based on query similarity."""
        # Simple keyword-based re-ranking
        query_words = set(query.lower().split())

        for result in results:
            content_words = set(result.get("content", "").lower().split())
            overlap = len(query_words.intersection(content_words))
            result["relevance_score"] = overlap / len(query_words) if query_words else 0

        return sorted(results, key=lambda x: x.get("relevance_score", 0), reverse=True)
