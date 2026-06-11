"""LLM-as-judge evaluation for RAG responses."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from src.config import settings
from src.generation.llm_client import OllamaClient

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    query_id: str
    faithfulness: float  # 0-1
    relevancy: float  # 0-1
    completeness: float  # 0-1
    overall: float  # 0-1
    issues: list[str]
    model_used: str
    cost_usd: float = 0.0


class LLMEvaluator:
    """Evaluate RAG responses using LLM-as-judge."""

    def __init__(self) -> None:
        self.llm = OllamaClient()
        self.judge_model = settings.ollama_simple_model

    def evaluate(
        self,
        query: str,
        answer: str,
        contexts: list[str],
        query_id: str = "",
    ) -> EvalResult:
        """Run full evaluation on a single query-answer pair."""
        faithfulness = self._check_faithfulness(query, answer, contexts)
        relevancy = self._check_relevancy(query, answer)
        completeness = self._check_completeness(query, answer)

        overall = (faithfulness + relevancy + completeness) / 3

        return EvalResult(
            query_id=query_id,
            faithfulness=faithfulness,
            relevancy=relevancy,
            completeness=completeness,
            overall=overall,
            issues=[],
            model_used=self.judge_model,
        )

    def _call_judge(self, prompt: str) -> str:
        resp = self.llm.chat(
            model=self.judge_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return resp.content

    def _parse_score(self, response: str, metric: str) -> float:
        """Extract a 0-1 score from judge response."""
        try:
            data = json.loads(response)
            return float(data.get(metric, 0)) / 10
        except (json.JSONDecodeError, ValueError):
            # Fallback: look for number in response
            import re
            numbers = re.findall(r"\d+\.?\d*", response)
            if numbers:
                return float(numbers[0]) / 10
            return 0.0

    def _check_faithfulness(
        self, query: str, answer: str, contexts: list[str]
    ) -> float:
        prompt = f"""Evaluate if this answer is faithful to the provided context.
Score 0-10 where:
- 10: All claims supported by context
- 5: Some claims supported, some not
- 0: Claims contradict context or are unsupported

Query: {query}
Context: {" ".join(contexts[:3])}
Answer: {answer}

Respond with JSON: {{"faithfulness": <score>, "reason": "<explanation>"}}"""

        response = self._call_judge(prompt)
        return self._parse_score(response, "faithfulness")

    def _check_relevancy(self, query: str, answer: str) -> float:
        prompt = f"""Evaluate if this answer is relevant to the query.
Score 0-10 where:
- 10: Directly answers the question
- 5: Partially relevant
- 0: Off-topic

Query: {query}
Answer: {answer}

Respond with JSON: {{"relevancy": <score>, "reason": "<explanation>"}}"""

        response = self._call_judge(prompt)
        return self._parse_score(response, "relevancy")

    def _check_completeness(self, query: str, answer: str) -> float:
        prompt = f"""Evaluate if this answer is complete.
Score 0-10 where:
- 10: Covers all aspects of the question
- 5: Partially covers the question
- 0: Missing most information

Query: {query}
Answer: {answer}

Respond with JSON: {{"completeness": <score>, "reason": "<explanation>"}}"""

        response = self._call_judge(prompt)
        return self._parse_score(response, "completeness")

    def run_evaluation(
        self, eval_pairs: list[dict], answers: dict[str, str]
    ) -> list[EvalResult]:
        """Run evaluation on a full set of query-answer pairs."""
        results: list[EvalResult] = []

        for pair in eval_pairs:
            qid = pair["id"]
            answer = answers.get(qid, "")
            contexts = pair.get("contexts", [])

            result = self.evaluate(
                query=pair["query"],
                answer=answer,
                contexts=contexts,
                query_id=qid,
            )
            results.append(result)
            logger.info(f"Evaluated {qid}: overall={result.overall:.2f}")

        return results
