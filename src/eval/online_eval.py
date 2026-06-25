"""Online evaluation — sample production traffic for quality measurement.

Runs LLM-as-Judge on a percentage of production queries to continuously
monitor answer quality, detect regressions, and feed the cost analytics dashboard.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OnlineEvalSample:
    """A single production query sampled for evaluation."""
    query: str
    answer: str
    model_used: str
    complexity: str
    latency_ms: float
    cost_usd: float
    timestamp: str
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    overall_score: float = 0.0
    evaluated: bool = False
    error: str = ""


class OnlineEvaluator:
    """Sample production traffic and evaluate with LLM-as-Judge.

    Usage:
        evaluator = OnlineEvaluator(sample_rate=0.05)  # 5% sampling
        if evaluator.should_sample():
            evaluator.sample_and_evaluate(
                query="What is MSFT revenue?",
                answer="Microsoft reported $245B...",
                model_used="gemma3:4b",
                ...
            )
    """

    def __init__(
        self,
        sample_rate: float = 0.05,
        output_dir: str | Path | None = None,
    ):
        self.sample_rate = sample_rate
        self.output_dir = Path(output_dir) if output_dir else settings.data_dir / "online_eval"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._judge = None

    def _get_judge(self):
        """Lazy-load LLM judge."""
        if self._judge is None:
            try:
                from src.eval.llm_judge import LLMJudge
                self._judge = LLMJudge()
            except Exception as e:
                logger.warning(f"LLM judge unavailable for online eval: {e}")
        return self._judge

    def should_sample(self) -> bool:
        """Determine if this query should be sampled for evaluation."""
        return random.random() < self.sample_rate

    def sample_and_evaluate(
        self,
        query: str,
        answer: str,
        model_used: str = "",
        complexity: str = "",
        latency_ms: float = 0.0,
        cost_usd: float = 0.0,
        contexts: list[str] | None = None,
        ground_truth: str = "",
    ) -> OnlineEvalSample | None:
        """Sample a production query and evaluate it.

        Args:
            query: User query
            answer: Generated answer
            model_used: Model used for generation
            complexity: Query complexity
            latency_ms: Response latency
            cost_usd: Cost of the query
            contexts: Retrieved contexts (if available)
            ground_truth: Expected answer (if available)

        Returns:
            OnlineEvalSample with scores (or None if evaluation fails)
        """
        sample = OnlineEvalSample(
            query=query,
            answer=answer,
            model_used=model_used,
            complexity=complexity,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            timestamp=datetime.now(UTC).isoformat(),
        )

        judge = self._get_judge()
        if judge is None:
            sample.error = "LLM judge unavailable"
            self._save_sample(sample)
            return sample

        # Use answer as ground truth if not provided (unsupervised evaluation)
        if not ground_truth:
            ground_truth = answer  # Self-consistency check

        if not contexts:
            contexts = [answer]  # Use answer as context for relevance check

        try:
            result = judge.evaluate(
                question=query,
                answer=answer,
                contexts=contexts,
                ground_truth=ground_truth,
            )
            sample.faithfulness = result.faithfulness
            sample.answer_relevancy = result.answer_relevancy
            sample.context_precision = result.context_precision
            sample.context_recall = result.context_recall
            sample.overall_score = (
                result.faithfulness * 0.3
                + result.answer_relevancy * 0.3
                + result.context_precision * 0.2
                + result.context_recall * 0.2
            )
            sample.evaluated = True

        except Exception as e:
            sample.error = str(e)
            logger.warning(f"Online eval failed for query: {e}")

        self._save_sample(sample)
        return sample

    def _save_sample(self, sample: OnlineEvalSample) -> None:
        """Save sample to daily JSONL file."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        filepath = self.output_dir / f"online_eval_{today}.jsonl"

        with open(filepath, "a") as f:
            f.write(json.dumps(asdict(sample), default=str) + "\n")

    def get_daily_stats(self, date: str | None = None) -> dict:
        """Get evaluation stats for a given date."""
        if date is None:
            date = datetime.now(UTC).strftime("%Y-%m-%d")

        filepath = self.output_dir / f"online_eval_{date}.jsonl"
        if not filepath.exists():
            return {"date": date, "total_samples": 0}

        samples = []
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))

        evaluated = [s for s in samples if s.get("evaluated")]
        if not evaluated:
            return {"date": date, "total_samples": len(samples), "evaluated": 0}

        return {
            "date": date,
            "total_samples": len(samples),
            "evaluated": len(evaluated),
            "avg_faithfulness": round(sum(s["faithfulness"] for s in evaluated) / len(evaluated), 4),
            "avg_relevancy": round(sum(s["answer_relevancy"] for s in evaluated) / len(evaluated), 4),
            "avg_overall": round(sum(s["overall_score"] for s in evaluated) / len(evaluated), 4),
            "avg_latency_ms": round(sum(s["latency_ms"] for s in evaluated) / len(evaluated), 2),
            "model_distribution": self._model_distribution(evaluated),
        }

    def _model_distribution(self, samples: list[dict]) -> dict[str, int]:
        """Count samples per model."""
        dist: dict[str, int] = {}
        for s in samples:
            model = s.get("model_used", "unknown")
            dist[model] = dist.get(model, 0) + 1
        return dist


# Singleton
online_evaluator = OnlineEvaluator()
