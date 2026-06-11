#!/usr/bin/env python3
"""Demo RAGAS evaluation with mock data (no external services needed)."""

from __future__ import annotations

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.eval.ragas_eval import RAGASEvaluator, EvalResult, save_eval_results
from src.eval.retrieval_metrics import evaluate_retrieval, RetrievalResult


def run_demo_evaluation():
    """Run demo evaluation with mock data."""
    print("=" * 60)
    print("RAGAS Evaluation Demo (Mock Data)")
    print("=" * 60)

    evaluator = RAGASEvaluator()

    # Mock test cases
    test_cases = [
        {
            "question": "What was Microsoft's revenue in 2024?",
            "answer": "Microsoft reported revenue of $245.1 billion for fiscal year 2024.",
            "contexts": ["Microsoft Corporation (MSFT) reported annual revenue of $245.1 billion for the fiscal year 2024."],
            "ground_truth": "Microsoft revenue was $245.1 billion in 2024",
        },
        {
            "question": "Compare Amazon and Microsoft revenue",
            "answer": "Amazon reported $574.0B revenue while Microsoft reported $245.1B in 2024.",
            "contexts": ["Amazon.com, Inc. (AMZN) revenue: $574.0 billion", "Microsoft Corporation (MSFT) revenue: $245.1 billion"],
            "ground_truth": "Amazon $574.0B, Microsoft $245.1B",
        },
        {
            "question": "What are Tesla's main risk factors?",
            "answer": "Tesla faces risks from EV competition, manufacturing scalability, and regulatory changes.",
            "contexts": ["Tesla Inc (TSLA) risk factors include: competition in EV market, manufacturing challenges, regulatory environment"],
            "ground_truth": "EV competition, manufacturing, regulatory risks",
        },
    ]

    # Run evaluation
    print("\n1. Running RAGAS evaluation...")
    eval_results = []
    for i, tc in enumerate(test_cases, 1):
        print(f"\n   [{i}/{len(test_cases)}] {tc['question'][:50]}...")
        result = evaluator.evaluate(
            question=tc["question"],
            answer=tc["answer"],
            contexts=tc["contexts"],
            ground_truth=tc["ground_truth"],
        )
        eval_results.append(result)
        print(f"   Faithfulness: {result.faithfulness:.3f}")
        print(f"   Answer Relevancy: {result.answer_relevancy:.3f}")
        print(f"   Context Precision: {result.context_precision:.3f}")
        print(f"   Context Recall: {result.context_recall:.3f}")

    # Compute metrics
    print("\n2. Computing aggregate metrics...")
    metrics = evaluator.compute_metrics(eval_results)

    print("\n" + "=" * 60)
    print("RAGAS EVALUATION RESULTS")
    print("=" * 60)
    print(f"Faithfulness:      {metrics['faithfulness']:.4f}")
    print(f"Answer Relevancy:  {metrics['answer_relevancy']:.4f}")
    print(f"Context Precision: {metrics['context_precision']:.4f}")
    print(f"Context Recall:    {metrics['context_recall']:.4f}")
    print(f"Overall Score:     {metrics['overall_score']:.4f}")
    print(f"Num Samples:       {metrics['num_samples']}")
    print("=" * 60)

    # Save results
    output_dir = project_root / "data" / "eval"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "ragas_results.json"
    save_eval_results(eval_results, metrics, str(output_path))
    print(f"\nResults saved to: {output_path}")

    # Run retrieval metrics demo
    print("\n" + "=" * 60)
    print("RETRIEVAL METRICS DEMO")
    print("=" * 60)

    def mock_retriever(query):
        # Mock retrieval returning document IDs
        return ["MSFT_2024", "AMZN_2024", "TSLA_2024", "GOOG_2024", "META_2024"]

    queries = [
        {"query": "Microsoft revenue", "relevant_ids": {"MSFT_2024"}},
        {"query": "Amazon revenue", "relevant_ids": {"AMZN_2024"}},
        {"query": "Tesla risks", "relevant_ids": {"TSLA_2024"}},
    ]

    retrieval_result = evaluate_retrieval(queries, mock_retriever)

    print(f"\nNDCG@10:         {retrieval_result.ndcg_at_10:.4f}")
    print(f"MRR:             {retrieval_result.mrr:.4f}")
    print(f"Recall@5:        {retrieval_result.recall_at_5:.4f}")
    print(f"Recall@10:       {retrieval_result.recall_at_10:.4f}")
    print(f"Precision@5:     {retrieval_result.precision_at_5:.4f}")
    print(f"Precision@10:    {retrieval_result.precision_at_10:.4f}")
    print(f"Hit Rate:        {retrieval_result.hit_rate:.4f}")
    print(f"Total Queries:   {retrieval_result.total_queries}")

    # Save retrieval results
    retrieval_path = output_dir / "retrieval_metrics.json"
    with open(retrieval_path, "w") as f:
        json.dump({
            "ndcg_at_10": retrieval_result.ndcg_at_10,
            "mrr": retrieval_result.mrr,
            "recall_at_5": retrieval_result.recall_at_5,
            "recall_at_10": retrieval_result.recall_at_10,
            "precision_at_5": retrieval_result.precision_at_5,
            "precision_at_10": retrieval_result.precision_at_10,
            "hit_rate": retrieval_result.hit_rate,
            "total_queries": retrieval_result.total_queries,
            "per_query": retrieval_result.per_query,
        }, f, indent=2)
    print(f"\nRetrieval metrics saved to: {retrieval_path}")

    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_demo_evaluation()
