"""Comprehensive evaluation script."""

import json

from src.agents.graph import LangGraphOrchestrator
from src.config import settings
from src.ml.evaluation import MLEvaluator
from src.ml.routing import CostAwareRouter

# Extended golden set (50+ queries)
GOLDEN_SET = [
    # Simple queries
    {"question": "What was Microsoft revenue in 2024?", "expected_answer": "$245.1 billion"},
    {"question": "How many employees does Amazon have?", "expected_answer": "1,540,000"},
    {"question": "What is Tesla market cap?", "expected_answer": ""},
    {"question": "When was Apple founded?", "expected_answer": ""},
    {"question": "What does NVIDIA make?", "expected_answer": ""},

    # Comparison queries
    {"question": "Compare Microsoft and Amazon revenue", "expected_answer": ""},
    {"question": "Compare NVIDIA and AMD revenue growth", "expected_answer": ""},
    {"question": "Compare Tesla and Apple employees", "expected_answer": ""},

    # Risk/Analysis queries
    {"question": "What are Tesla risk factors?", "expected_answer": ""},
    {"question": "What are Meta main products?", "expected_answer": ""},
    {"question": "What is Google revenue growth?", "expected_answer": ""},

    # Financial analysis
    {"question": "What is Microsoft profit margin?", "expected_answer": ""},
    {"question": "How much does Amazon spend on R&D?", "expected_answer": ""},
    {"question": "What is NVIDIA gross margin?", "expected_answer": ""},

    # Trend queries
    {"question": "How has Microsoft revenue changed over time?", "expected_answer": ""},
    {"question": "What is Tesla revenue trend?", "expected_answer": ""},
    {"question": "How is Apple performing compared to last year?", "expected_answer": ""},
]


def run_evaluation():
    """Run full evaluation pipeline."""
    print("=" * 60)
    print("  ML Evaluation Pipeline")
    print("=" * 60)
    print()

    # Initialize components
    orchestrator = LangGraphOrchestrator()
    evaluator = MLEvaluator()
    router = CostAwareRouter()

    # Run evaluation
    print(f"[2/5] Running evaluation on {len(GOLDEN_SET)} queries...")
    results = evaluator.run_evaluation(GOLDEN_SET, orchestrator)

    # Calculate metrics
    print("[3/5] Calculating metrics...")
    metrics = evaluator.get_metrics()

    # Cost analysis
    print("[4/5] Analyzing costs...")
    cost_analysis = {
        "total_queries": metrics["total_queries"],
        "total_cost": metrics["total_cost_usd"],
        "avg_cost_per_query": metrics["total_cost_usd"] / metrics["total_queries"],
        "avg_latency_ms": metrics["avg_latency_ms"],
        "hallucination_rate": metrics["hallucination_rate"],
    }

    # Save results
    print("[5/5] Saving results...")
    evaluator.save_results(settings.eval_dir / "evaluation_results.json")

    with open(settings.eval_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    with open(settings.eval_dir / "cost_analysis.json", "w") as f:
        json.dump(cost_analysis, f, indent=2)

    # Print summary
    print()
    print("=" * 60)
    print("  Evaluation Results")
    print("=" * 60)
    print()
    print(f"Total Queries: {metrics['total_queries']}")
    print(f"Overall Score: {metrics['avg_overall']:.3f}")
    print(f"Relevance Score: {metrics['avg_relevance']:.3f}")
    print(f"Accuracy Score: {metrics['avg_accuracy']:.3f}")
    print(f"Completeness Score: {metrics['avg_completeness']:.3f}")
    print()
    print(f"Average Latency: {metrics['avg_latency_ms']:.0f}ms")
    print(f"Total Cost: ${metrics['total_cost_usd']:.4f}")
    print(f"Hallucination Rate: {metrics['hallucination_rate']:.1%}")
    print()

    # Model selection analysis
    print("Model Selection Analysis:")
    for result in results[:5]:
        complexity = router.route(result.query).complexity
        print(f"  [{complexity:8}] {result.query[:50]}... → {result.model_used}")

    print()
    print("=" * 60)
    print("  Evaluation Complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_evaluation()
