"""RAGAS evaluation framework for proper RAG assessment."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    """Result of a single evaluation."""
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0


class RAGASEvaluator:
    """RAGAS evaluation for RAG systems.

    Uses LLM-as-judge for faithfulness, answer relevancy, context precision, and context recall.
    Falls back to heuristic metrics if RAGAS is not available.
    """

    def __init__(self, llm=None):
        self.llm = llm
        self._ragas_available = False
        try:
            import ragas
            self._ragas_available = True
            logger.info("RAGAS available for evaluation")
        except ImportError:
            logger.warning("RAGAS not installed, using heuristic evaluation")

    def evaluate(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str,
    ) -> EvalResult:
        """Evaluate a single Q&A pair."""
        result = EvalResult(
            question=question,
            answer=answer,
            contexts=contexts,
            ground_truth=ground_truth,
        )

        if self._ragas_available:
            return self._evaluate_with_ragas(result)
        else:
            return self._evaluate_with_heuristics(result)

    def _evaluate_with_ragas(self, result: EvalResult) -> EvalResult:
        """Evaluate using RAGAS framework."""
        try:
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            )
            from datasets import Dataset

            # Prepare data for RAGAS
            data = {
                "question": [result.question],
                "answer": [result.answer],
                "contexts": [result.contexts],
                "ground_truth": [result.ground_truth],
            }

            dataset = Dataset.from_dict(data)

            # Run evaluation
            eval_result = evaluate(
                dataset,
                metrics=[
                    faithfulness,
                    answer_relevancy,
                    context_precision,
                    context_recall,
                ],
            )

            result.faithfulness = eval_result["faithfulness"]
            result.answer_relevancy = eval_result["answer_relevancy"]
            result.context_precision = eval_result["context_precision"]
            result.context_recall = eval_result["context_recall"]

        except Exception as e:
            logger.warning(f"RAGAS evaluation failed, falling back to heuristics: {e}")
            return self._evaluate_with_heuristics(result)

        return result

    def _evaluate_with_heuristics(self, result: EvalResult) -> EvalResult:
        """Evaluate using heuristic metrics."""
        answer_lower = result.answer.lower()
        ground_truth_lower = result.ground_truth.lower()

        # Faithfulness: check if answer mentions key facts from ground truth
        ground_truth_words = set(ground_truth_lower.split())
        answer_words = set(answer_lower.split())
        if ground_truth_words:
            overlap = len(ground_truth_words & answer_words)
            result.faithfulness = min(1.0, overlap / len(ground_truth_words) * 1.5)
        else:
            result.faithfulness = 0.5

        # Answer relevancy: check if answer addresses the question
        question_words = set(result.question.lower().split())
        if question_words:
            answer_relevant = len(question_words & answer_words) / len(question_words)
            result.answer_relevancy = min(1.0, answer_relevant * 1.2)
        else:
            result.answer_relevancy = 0.5

        # Context precision: check if contexts are relevant to question
        if result.contexts:
            context_text = " ".join(result.contexts).lower()
            context_words = set(context_text.split())
            if question_words:
                result.context_precision = min(1.0, len(question_words & context_words) / len(question_words))
            else:
                result.context_precision = 0.5
        else:
            result.context_precision = 0.0

        # Context recall: check if contexts contain ground truth info
        if result.contexts and ground_truth_words:
            context_text = " ".join(result.contexts).lower()
            context_words = set(context_text.split())
            result.context_recall = min(1.0, len(ground_truth_words & context_words) / len(ground_truth_words))
        else:
            result.context_recall = 0.0

        return result

    def evaluate_batch(
        self,
        eval_data: list[dict],
    ) -> list[EvalResult]:
        """Evaluate a batch of Q&A pairs."""
        results = []
        for item in eval_data:
            result = self.evaluate(
                question=item["question"],
                answer=item["answer"],
                contexts=item.get("contexts", []),
                ground_truth=item["ground_truth"],
            )
            results.append(result)
        return results

    def compute_metrics(self, results: list[EvalResult]) -> dict:
        """Compute aggregate metrics from evaluation results."""
        if not results:
            return {
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "context_precision": 0.0,
                "context_recall": 0.0,
                "overall_score": 0.0,
                "num_samples": 0,
            }

        n = len(results)
        faithfulness = sum(r.faithfulness for r in results) / n
        answer_relevancy = sum(r.answer_relevancy for r in results) / n
        context_precision = sum(r.context_precision for r in results) / n
        context_recall = sum(r.context_recall for r in results) / n

        overall_score = (
            faithfulness * 0.3
            + answer_relevancy * 0.3
            + context_precision * 0.2
            + context_recall * 0.2
        )

        return {
            "faithfulness": round(faithfulness, 4),
            "answer_relevancy": round(answer_relevancy, 4),
            "context_precision": round(context_precision, 4),
            "context_recall": round(context_recall, 4),
            "overall_score": round(overall_score, 4),
            "num_samples": n,
        }


# ── Golden Dataset ────────────────────────────────────────────────

GOLDEN_DATASET = [
    {
        "question": "What was Microsoft's total revenue in fiscal year 2024?",
        "ground_truth": "Microsoft reported total revenue of $245.1 billion for fiscal year 2024.",
        "expected_tickers": ["MSFT"],
        "expected_years": ["2024"],
    },
    {
        "question": "How many employees does Amazon have?",
        "ground_truth": "Amazon had approximately 1,556,000 full-time and part-time employees.",
        "expected_tickers": ["AMZN"],
        "expected_years": ["2024"],
    },
    {
        "question": "Compare Tesla and Amazon revenue growth from 2023 to 2024.",
        "ground_truth": "Tesla revenue grew from $96.8B to $97.7B (0.9% growth). Amazon revenue grew from $574.8B to $638.0B (11.0% growth).",
        "expected_tickers": ["TSLA", "AMZN"],
        "expected_years": ["2023", "2024"],
    },
    {
        "question": "What are Microsoft's main business segments?",
        "ground_truth": "Microsoft operates through three main segments: Productivity and Business Processes, Intelligent Cloud, and More Personal Computing.",
        "expected_tickers": ["MSFT"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Alphabet's revenue breakdown by segment?",
        "ground_truth": "Alphabet's revenue comes primarily from Google Services (Search, YouTube, Android, Chrome, Google Maps, Google Play, hardware) and Google Cloud.",
        "expected_tickers": ["GOOG"],
        "expected_years": ["2024"],
    },
    {
        "question": "How many employees does Meta have and how has it changed?",
        "ground_truth": "Meta had approximately 72,404 employees in 2024, down from 67,317 in 2023.",
        "expected_tickers": ["META"],
        "expected_years": ["2023", "2024"],
    },
    {
        "question": "What are Tesla's main risk factors?",
        "ground_truth": "Tesla's key risks include competition in the EV market, dependency on Elon Musk, supply chain challenges, regulatory risks, and manufacturing scaling.",
        "expected_tickers": ["TSLA"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Amazon Web Services revenue?",
        "ground_truth": "AWS revenue was approximately $105.2 billion in 2024.",
        "expected_tickers": ["AMZN"],
        "expected_years": ["2024"],
    },
    {
        "question": "Compare Microsoft and Google cloud revenue.",
        "ground_truth": "Microsoft Intelligent Cloud revenue was approximately $105.4B. Google Cloud revenue was approximately $43.6B.",
        "expected_tickers": ["MSFT", "GOOG"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Apple's total revenue?",
        "ground_truth": "Apple reported total revenue of $391.0 billion for fiscal year 2024.",
        "expected_tickers": ["AAPL"],
        "expected_years": ["2024"],
    },
]


def load_golden_dataset() -> list[dict]:
    """Load the golden dataset for evaluation."""
    return GOLDEN_DATASET


def save_eval_results(results: list[EvalResult], metrics: dict, output_path: str) -> None:
    """Save evaluation results to file."""
    output = {
        "metrics": metrics,
        "results": [
            {
                "question": r.question,
                "answer": r.answer,
                "ground_truth": r.ground_truth,
                "faithfulness": r.faithfulness,
                "answer_relevancy": r.answer_relevancy,
                "context_precision": r.context_precision,
                "context_recall": r.context_recall,
            }
            for r in results
        ],
    }

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Eval results saved to {path}")
