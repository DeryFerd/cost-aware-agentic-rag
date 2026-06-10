#!/usr/bin/env python3
"""Run RAGAS evaluation on the RAG system."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.eval.ragas_eval import (
    RAGASEvaluator,
    load_golden_dataset,
    save_eval_results,
)
from src.agents.graph import LangGraphOrchestrator
from src.retrieval.hybrid import HybridRetriever


def run_evaluation():
    """Run full RAGAS evaluation."""
    print("=" * 60)
    print("RAGAS Evaluation for Cost-Aware Agentic RAG")
    print("=" * 60)

    # Initialize components
    print("\n1. Initializing components...")
    retriever = HybridRetriever()
    retriever.load_indices()

    orchestrator = LangGraphOrchestrator()
    evaluator = RAGASEvaluator()

    # Load golden dataset
    print("\n2. Loading golden dataset...")
    golden_data = load_golden_dataset()
    print(f"   Loaded {len(golden_data)} test cases")

    # Run evaluation
    print("\n3. Running evaluation...")
    eval_results = []

    for i, item in enumerate(golden_data, 1):
        print(f"\n   [{i}/{len(golden_data)}] {item['question'][:60]}...")

        # Get answer from system
        try:
            response = orchestrator.run(item["question"])
            answer = response["answer"]
        except Exception as e:
            print(f"   ERROR: {e}")
            answer = f"Error: {e}"

        # Get contexts from retriever
        try:
            results = retriever.retrieve(item["question"], top_k=5)
            contexts = [r.text for r in results]
        except Exception as e:
            print(f"   Retrieval error: {e}")
            contexts = []

        # Evaluate
        result = evaluator.evaluate(
            question=item["question"],
            answer=answer,
            contexts=contexts,
            ground_truth=item["ground_truth"],
        )
        eval_results.append(result)

        print(f"   Faithfulness: {result.faithfulness:.3f}")
        print(f"   Answer Relevancy: {result.answer_relevancy:.3f}")
        print(f"   Context Precision: {result.context_precision:.3f}")
        print(f"   Context Recall: {result.context_recall:.3f}")

    # Compute metrics
    print("\n4. Computing aggregate metrics...")
    metrics = evaluator.compute_metrics(eval_results)

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"Faithfulness:      {metrics['faithfulness']:.4f}")
    print(f"Answer Relevancy:  {metrics['answer_relevancy']:.4f}")
    print(f"Context Precision: {metrics['context_precision']:.4f}")
    print(f"Context Recall:    {metrics['context_recall']:.4f}")
    print(f"Overall Score:     {metrics['overall_score']:.4f}")
    print(f"Num Samples:       {metrics['num_samples']}")
    print("=" * 60)

    # Save results
    output_path = project_root / "data" / "eval" / "ragas_results.json"
    save_eval_results(eval_results, metrics, str(output_path))
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    run_evaluation()
