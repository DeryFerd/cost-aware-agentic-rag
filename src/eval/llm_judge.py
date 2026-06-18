"""LLM-as-Judge evaluation using Ollama Cloud.

Implements RAGAS-style metrics (faithfulness, answer relevancy, context precision,
context recall) using LLM scoring instead of word overlap.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

# Judge model — use a capable model for evaluation
JUDGE_MODEL = "minimax-m3:cloud"


@dataclass
class LLMEvalResult:
    """Result of LLM-as-judge evaluation."""
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0


class LLMJudge:
    """LLM-as-judge evaluator for RAG systems.

    Uses a capable LLM to score faithfulness, relevancy, precision, and recall
    on a 0-1 scale, much more accurate than word-overlap heuristics.
    """

    def __init__(self, model: str = JUDGE_MODEL):
        self.llm = ChatOpenAI(
            base_url=f"{settings.ollama_host}/v1",
            api_key=settings.ollama_api_key,
            model=model,
            temperature=0.0,
            max_tokens=100,
        )
        self.model = model

    def _score(self, system_prompt: str, user_prompt: str) -> float:
        """Get a 0-1 score from the LLM judge."""
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            resp = self.llm.invoke(messages)
            text = resp.content.strip()

            # Extract numeric score (look for 0.X or X/10 patterns)
            import re
            # Try 0.X pattern
            match = re.search(r'(\d+\.\d+)', text)
            if match:
                score = float(match.group(1))
                if score <= 1.0:
                    return score
                elif score <= 10.0:
                    return score / 10.0

            # Try single digit
            match = re.search(r'(\d)', text)
            if match:
                score = float(match.group(1))
                if score <= 10:
                    return score / 10.0

            logger.warning(f"Could not parse score from: {text}")
            return 0.5

        except Exception as e:
            logger.warning(f"LLM judge failed: {e}")
            return 0.5

    def faithfulness(self, answer: str, contexts: list[str]) -> float:
        """Score: Is the answer grounded in the provided contexts?

        1.0 = fully supported by context
        0.0 = completely hallucinated
        """
        context_text = "\n".join(contexts[:5])  # limit to 5 contexts
        system = "You are a precise evaluator. Score from 0.0 to 1.0 only."
        user = f"""Rate how well the ANSWER is supported by the CONTEXTS.
Score 1.0 if every claim in the answer is directly supported.
Score 0.5 if some claims are supported but others are not.
Score 0.0 if the answer contradicts or is unrelated to contexts.

CONTEXTS:
{context_text}

ANSWER: {answer}

Score (0.0-1.0):"""
        return self._score(system, user)

    def answer_relevancy(self, question: str, answer: str) -> float:
        """Score: Does the answer address the question?

        1.0 = directly answers the question
        0.0 = completely irrelevant
        """
        system = "You are a precise evaluator. Score from 0.0 to 1.0 only."
        user = f"""Rate how well the ANSWER addresses the QUESTION.
Score 1.0 if it directly and completely answers.
Score 0.5 if it partially addresses the question.
Score 0.0 if it's irrelevant or off-topic.

QUESTION: {question}

ANSWER: {answer}

Score (0.0-1.0):"""
        return self._score(system, user)

    def context_precision(self, question: str, contexts: list[str]) -> float:
        """Score: Are the retrieved contexts relevant to the question?

        1.0 = all contexts are relevant
        0.0 = no contexts are relevant
        """
        context_text = "\n".join(contexts[:5])
        system = "You are a precise evaluator. Score from 0.0 to 1.0 only."
        user = f"""Rate how relevant the CONTEXTS are to the QUESTION.
Score 1.0 if all contexts are directly relevant.
Score 0.5 if some contexts are relevant.
Score 0.0 if no contexts are relevant.

QUESTION: {question}

CONTEXTS:
{context_text}

Score (0.0-1.0):"""
        return self._score(system, user)

    def context_recall(self, ground_truth: str, contexts: list[str]) -> float:
        """Score: Do the contexts contain the ground truth information?

        1.0 = all ground truth info is in contexts
        0.0 = none of the ground truth info is in contexts
        """
        context_text = "\n".join(contexts[:5])
        system = "You are a precise evaluator. Score from 0.0 to 1.0 only."
        user = f"""Rate how well the CONTEXTS cover the GROUND TRUTH information.
Score 1.0 if all ground truth facts appear in contexts.
Score 0.5 if some ground truth facts appear.
Score 0.0 if none of the ground truth is in contexts.

GROUND TRUTH: {ground_truth}

CONTEXTS:
{context_text}

Score (0.0-1.0):"""
        return self._score(system, user)

    def evaluate(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str,
    ) -> LLMEvalResult:
        """Evaluate a single Q&A pair with all 4 metrics."""
        result = LLMEvalResult(
            question=question,
            answer=answer,
            contexts=contexts,
            ground_truth=ground_truth,
        )

        result.faithfulness = self.faithfulness(answer, contexts)
        result.answer_relevancy = self.answer_relevancy(question, answer)
        result.context_precision = self.context_precision(question, contexts)
        result.context_recall = self.context_recall(ground_truth, contexts)

        return result

    def evaluate_batch(self, eval_data: list[dict]) -> list[LLMEvalResult]:
        """Evaluate a batch of Q&A pairs."""
        results = []
        for i, item in enumerate(eval_data):
            logger.info(f"Evaluating [{i+1}/{len(eval_data)}]: {item['question'][:50]}...")
            result = self.evaluate(
                question=item["question"],
                answer=item["answer"],
                contexts=item.get("contexts", []),
                ground_truth=item["ground_truth"],
            )
            results.append(result)
        return results

    @staticmethod
    def compute_metrics(results: list[LLMEvalResult]) -> dict:
        """Compute aggregate metrics."""
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

        overall = (
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
            "overall_score": round(overall, 4),
            "num_samples": n,
        }


def save_llm_eval_results(results: list[LLMEvalResult], metrics: dict, output_path: str) -> None:
    """Save LLM judge evaluation results."""
    output = {
        "judge_model": JUDGE_MODEL,
        "metrics": metrics,
        "results": [
            {
                "question": r.question,
                "answer": r.answer[:200],
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

    logger.info(f"LLM eval results saved to {path}")
