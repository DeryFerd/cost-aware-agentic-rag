"""Run evaluation on the golden set."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.eval.evaluator import LLMEvaluator
from src.eval.golden_set import get_golden_set
from src.agents.orchestrator import AgenticOrchestrator
import json


def run_evaluation():
    """Run full evaluation on the golden set."""
    print("=" * 60)
    print("  FinRAG Evaluation Harness")
    print("=" * 60)

    # Initialize
    orchestrator = AgenticOrchestrator()
    orchestrator.retriever.load_indices()
    evaluator = LLMEvaluator()

    # Get golden set
    golden_set = get_golden_set()
    print(f"\n  Evaluating {len(golden_set)} queries...")

    results = []
    for i, item in enumerate(golden_set):
        print(f"\n[{i+1}/{len(golden_set)}] {item['query']}")

        # Run query
        response = orchestrator.run(item["query"])
        print(f"  Answer: {response.answer[:80]}...")

        # Get contexts from retrieval
        retrieval_results = orchestrator.retriever.retrieve(item["query"], top_k=3)
        contexts = [r.text for r in retrieval_results]

        # Evaluate
        eval_result = evaluator.evaluate(
            query=item["query"],
            answer=response.answer,
            contexts=contexts,
            query_id=item["id"],
        )

        results.append({
            "id": item["id"],
            "query": item["query"],
            "expected": item["expected_answer"],
            "actual": response.answer,
            "faithfulness": eval_result.faithfulness,
            "relevancy": eval_result.relevancy,
            "completeness": eval_result.completeness,
            "overall": eval_result.overall,
        })

        print(f"  Scores: F={eval_result.faithfulness:.2f} R={eval_result.relevancy:.2f} C={eval_result.completeness:.2f} Overall={eval_result.overall:.2f}")

    # Save results
    output_path = project_root / "data" / "eval" / "eval_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    print(f"\n{'=' * 60}")
    print("  Evaluation Summary")
    print(f"{'=' * 60}")

    avg_faithfulness = sum(r["faithfulness"] for r in results) / len(results)
    avg_relevancy = sum(r["relevancy"] for r in results) / len(results)
    avg_completeness = sum(r["completeness"] for r in results) / len(results)
    avg_overall = sum(r["overall"] for r in results) / len(results)

    print(f"  Faithfulness:  {avg_faithfulness:.2f}/1.00")
    print(f"  Relevancy:     {avg_relevancy:.2f}/1.00")
    print(f"  Completeness:  {avg_completeness:.2f}/1.00")
    print(f"  Overall:       {avg_overall:.2f}/1.00")
    print(f"\n  Results saved to: {output_path}")


if __name__ == "__main__":
    run_evaluation()
