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
            import ragas  # noqa: F401
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
        """Evaluate using heuristic metrics.

        Uses token overlap, bigram overlap, and cosine-like similarity
        for more accurate heuristic scoring than simple word overlap.
        """
        answer_tokens = result.answer.lower().split()
        gt_tokens = result.ground_truth.lower().split()
        q_tokens = result.question.lower().split()

        # Faithfulness: bigram overlap between answer and ground truth
        answer_bigrams = self._get_bigrams(answer_tokens)
        gt_bigrams = self._get_bigrams(gt_tokens)
        if gt_bigrams:
            bigram_overlap = len(answer_bigrams & gt_bigrams) / len(gt_bigrams)
            # Also consider unigram overlap
            unigram_overlap = len(set(answer_tokens) & set(gt_tokens)) / len(set(gt_tokens)) if gt_tokens else 0
            result.faithfulness = min(1.0, 0.6 * bigram_overlap + 0.4 * unigram_overlap)
        else:
            result.faithfulness = 0.5

        # Answer relevancy: token overlap with question
        if q_tokens:
            q_set = set(q_tokens)
            a_set = set(answer_tokens)
            relevant = len(q_set & a_set) / len(q_set)
            # Penalize very short answers
            length_factor = min(1.0, len(answer_tokens) / 10)
            result.answer_relevancy = min(1.0, relevant * length_factor)
        else:
            result.answer_relevancy = 0.5

        # Context precision: how many question tokens appear in contexts
        if result.contexts:
            ctx_text = " ".join(result.contexts).lower()
            ctx_tokens = set(ctx_text.split())
            if q_tokens:
                q_set = set(q_tokens)
                result.context_precision = min(1.0, len(q_set & ctx_tokens) / len(q_set))
            else:
                result.context_precision = 0.5
        else:
            result.context_precision = 0.0

        # Context recall: how many ground truth tokens appear in contexts
        if result.contexts and gt_tokens:
            ctx_text = " ".join(result.contexts).lower()
            ctx_tokens = set(ctx_text.split())
            gt_set = set(gt_tokens)
            result.context_recall = min(1.0, len(gt_set & ctx_tokens) / len(gt_set))
        else:
            result.context_recall = 0.0

        return result

    @staticmethod
    def _get_bigrams(tokens: list[str]) -> set[tuple[str, str]]:
        """Extract bigrams from token list."""
        return {(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)}

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
    {
        "question": "What is Microsoft's net income for 2024?",
        "ground_truth": "Microsoft reported net income of $88.1 billion for fiscal year 2024.",
        "expected_tickers": ["MSFT"],
        "expected_years": ["2024"],
    },
    {
        "question": "How much did Amazon spend on R&D in 2024?",
        "ground_truth": "Amazon spent approximately $85.6 billion on research and development in 2024.",
        "expected_tickers": ["AMZN"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Tesla's gross margin?",
        "ground_truth": "Tesla's automotive gross margin was approximately 17.9% in 2024.",
        "expected_tickers": ["TSLA"],
        "expected_years": ["2024"],
    },
    {
        "question": "How many devices does Apple have in active install base?",
        "ground_truth": "Apple reported over 2.2 billion active devices worldwide.",
        "expected_tickers": ["AAPL"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Meta's operating income?",
        "ground_truth": "Meta reported operating income of approximately $52.0 billion in 2024.",
        "expected_tickers": ["META"],
        "expected_years": ["2024"],
    },
    {
        "question": "Compare Amazon and Microsoft operating income.",
        "ground_truth": "Amazon operating income was approximately $68.9B. Microsoft operating income was approximately $109.4B.",
        "expected_tickers": ["AMZN", "MSFT"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Google's advertising revenue?",
        "ground_truth": "Google advertising revenue was approximately $264.7 billion in 2024.",
        "expected_tickers": ["GOOG"],
        "expected_years": ["2024"],
    },
    {
        "question": "What are Amazon's business segments?",
        "ground_truth": "Amazon operates through three segments: North America, International, and Amazon Web Services (AWS).",
        "expected_tickers": ["AMZN"],
        "expected_years": ["2024"],
    },
    {
        "question": "How much did Tesla deliver in vehicles?",
        "ground_truth": "Tesla delivered approximately 1.79 million vehicles in 2024.",
        "expected_tickers": ["TSLA"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Apple's services revenue?",
        "ground_truth": "Apple Services revenue was approximately $96.2 billion in fiscal year 2024.",
        "expected_tickers": ["AAPL"],
        "expected_years": ["2024"],
    },
    {
        "question": "Compare Tesla and Rivian risk factors.",
        "ground_truth": "Tesla risks: EV competition, Musk dependency, supply chain, regulatory. Rivian risks: production scaling, cash burn, competition with established automakers.",
        "expected_tickers": ["TSLA", "RIVN"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Microsoft's capital expenditure?",
        "ground_truth": "Microsoft capital expenditure was approximately $44.5 billion in fiscal year 2024.",
        "expected_tickers": ["MSFT"],
        "expected_years": ["2024"],
    },
    {
        "question": "How much does Alphabet invest in AI?",
        "ground_truth": "Alphabet's capital expenditure on AI and infrastructure was approximately $32.3 billion in 2024.",
        "expected_tickers": ["GOOG"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Meta's reality labs revenue?",
        "ground_truth": "Meta's Reality Labs segment generated approximately $2.1 billion in revenue in 2024.",
        "expected_tickers": ["META"],
        "expected_years": ["2024"],
    },
    {
        "question": "Compare R&D spending across FAANG companies.",
        "ground_truth": "Amazon R&D: $85.6B, Google R&D: $49.3B, Meta R&D: $39.5B, Apple R&D: $30.5B, Netflix R&D: ~$2.5B.",
        "expected_tickers": ["AMZN", "GOOG", "META", "AAPL", "NFLX"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Amazon's free cash flow?",
        "ground_truth": "Amazon's free cash flow was approximately $46.9 billion in 2024.",
        "expected_tickers": ["AMZN"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Tesla's energy generation revenue?",
        "ground_truth": "Tesla's energy generation and storage revenue was approximately $10.1 billion in 2024.",
        "expected_tickers": ["TSLA"],
        "expected_years": ["2024"],
    },
    {
        "question": "How many data centers does Microsoft operate?",
        "ground_truth": "Microsoft operates over 60 data center regions worldwide as of 2024.",
        "expected_tickers": ["MSFT"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Apple's net cash position?",
        "ground_truth": "Apple had net cash of approximately $62.4 billion as of 2024.",
        "expected_tickers": ["AAPL"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Google's total number of employees?",
        "ground_truth": "Alphabet had approximately 183,323 employees in 2024.",
        "expected_tickers": ["GOOG"],
        "expected_years": ["2024"],
    },
    {
        "question": "Compare cloud revenue growth of AWS, Azure, and Google Cloud.",
        "ground_truth": "AWS revenue grew 19% YoY to $105.2B. Microsoft Azure grew 29%. Google Cloud grew 30% to $43.6B.",
        "expected_tickers": ["AMZN", "MSFT", "GOOG"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Tesla's vehicle margin?",
        "ground_truth": "Tesla's automotive margin was approximately 17.9% in 2024.",
        "expected_tickers": ["TSLA"],
        "expected_years": ["2024"],
    },
    {
        "question": "How much did Amazon return to shareholders?",
        "ground_truth": "Amazon repurchased approximately $6.0 billion in shares and paid $0.9 billion in dividends in 2024.",
        "expected_tickers": ["AMZN"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Microsoft's dividend yield?",
        "ground_truth": "Microsoft's annual dividend was $3.32 per share, yielding approximately 0.7%.",
        "expected_tickers": ["MSFT"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Alphabet's other bets revenue?",
        "ground_truth": "Alphabet's Other Bets revenue was approximately $1.5 billion in 2024.",
        "expected_tickers": ["GOOG"],
        "expected_years": ["2024"],
    },
    {
        "question": "How many subscribers does Netflix have?",
        "ground_truth": "Netflix had approximately 301 million paid subscribers globally.",
        "expected_tickers": ["NFLX"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Apple's operating margin?",
        "ground_truth": "Apple's operating margin was approximately 31.5% in fiscal year 2024.",
        "expected_tickers": ["AAPL"],
        "expected_years": ["2024"],
    },
    {
        "question": "Compare Meta and Google advertising revenue.",
        "ground_truth": "Meta advertising revenue was approximately $160.2B. Google advertising revenue was approximately $264.7B.",
        "expected_tickers": ["META", "GOOG"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Tesla's debt level?",
        "ground_truth": "Tesla had approximately $7.4 billion in total debt as of end of 2024.",
        "expected_tickers": ["TSLA"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Amazon's operating cash flow?",
        "ground_truth": "Amazon's operating cash flow was approximately $115.9 billion in 2024.",
        "expected_tickers": ["AMZN"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Nvidia's revenue from data centers?",
        "ground_truth": "Nvidia data center revenue was approximately $115.2 billion in fiscal 2025.",
        "expected_tickers": ["NVDA"],
        "expected_years": ["2025"],
    },
    {
        "question": "How does Tesla's revenue compare to traditional automakers?",
        "ground_truth": "Tesla revenue $97.7B vs Toyota $284B, Volkswagen $295B, GM $171B in 2024.",
        "expected_tickers": ["TSLA"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Microsoft's AI revenue contribution?",
        "ground_truth": "Microsoft reported $13 billion in annual revenue from AI services, growing 175% YoY.",
        "expected_tickers": ["MSFT"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Google's YouTube revenue?",
        "ground_truth": "YouTube advertising revenue was approximately $36.1 billion in 2024.",
        "expected_tickers": ["GOOG"],
        "expected_years": ["2024"],
    },
    {
        "question": "Compare Tesla and BYD vehicle sales.",
        "ground_truth": "Tesla delivered 1.79M vehicles. BYD sold 4.27M vehicles (including hybrids) in 2024.",
        "expected_tickers": ["TSLA"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Apple's iPhone revenue?",
        "ground_truth": "Apple iPhone revenue was approximately $201.2 billion in fiscal year 2024.",
        "expected_tickers": ["AAPL"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Amazon's advertising revenue?",
        "ground_truth": "Amazon advertising revenue was approximately $56.2 billion in 2024.",
        "expected_tickers": ["AMZN"],
        "expected_years": ["2024"],
    },
    {
        "question": "How much did Meta spend on the metaverse?",
        "ground_truth": "Meta's Reality Labs operating loss was approximately $16.1 billion in 2024.",
        "expected_tickers": ["META"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Microsoft's gaming revenue?",
        "ground_truth": "Microsoft gaming revenue was approximately $21.5 billion in fiscal year 2024, driven by Xbox and Activision Blizzard.",
        "expected_tickers": ["MSFT"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Tesla's market share in EVs?",
        "ground_truth": "Tesla held approximately 18% global EV market share in 2024.",
        "expected_tickers": ["TSLA"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Alphabet's Waymo revenue?",
        "ground_truth": "Alphabet's Waymo autonomous driving unit was not broken out separately but operated in limited commercial areas.",
        "expected_tickers": ["GOOG"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Apple's wearables revenue?",
        "ground_truth": "Apple Wearables, Home and Accessories revenue was approximately $39.8 billion in fiscal year 2024.",
        "expected_tickers": ["AAPL"],
        "expected_years": ["2024"],
    },
    {
        "question": "How does AWS profitability compare to Azure?",
        "ground_truth": "AWS operating income was $39.8B with 38% margin. Azure margin was approximately 44%.",
        "expected_tickers": ["AMZN", "MSFT"],
        "expected_years": ["2024"],
    },
    {
        "question": "What is Netflix's revenue per subscriber?",
        "ground_truth": "Netflix average revenue per membership was approximately $12.50/month globally.",
        "expected_tickers": ["NFLX"],
        "expected_years": ["2024"],
    },
    {
        "question": "What are Nvidia's competitive advantages?",
        "ground_truth": "Nvidia advantages: CUDA ecosystem, developer lock-in, 90%+ AI chip market share, full-stack hardware+software platform.",
        "expected_tickers": ["NVDA"],
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
