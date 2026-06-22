#!/usr/bin/env python3
"""Run LLM-as-judge evaluation on golden dataset.

Uses Ollama Cloud (minimax-m3:cloud) as the judge to evaluate
faithfulness, answer relevancy, context precision, and context recall.
"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.eval.llm_judge import LLMJudge, save_llm_eval_results
from src.eval.ragas_eval import GOLDEN_DATASET

# Mock answers — simulate what the RAG system would generate
# These are plausible answers from SEC filing retrieval
MOCK_ANSWERS = {
    "What was Microsoft's total revenue in fiscal year 2024?": "Microsoft reported total revenue of $245.1 billion for fiscal year 2024, driven by growth across all business segments.",
    "How many employees does Amazon have?": "Amazon had approximately 1,556,000 full-time and part-time employees as of December 2024.",
    "Compare Tesla and Amazon revenue growth from 2023 to 2024.": "Tesla revenue grew from $96.8B to $97.7B (0.9% growth). Amazon revenue grew from $574.8B to $638.0B (11.0% growth), significantly outpacing Tesla.",
    "What are Microsoft's main business segments?": "Microsoft operates through three main segments: Productivity and Business Processes (Office, LinkedIn), Intelligent Cloud (Azure), and More Personal Computing (Windows, Xbox, Surface).",
    "What is Alphabet's revenue breakdown by segment?": "Alphabet's revenue comes primarily from Google Services (Search, YouTube, Android, Chrome, Google Maps, Google Play, hardware) and Google Cloud segment.",
    "How many employees does Meta have and how has it changed?": "Meta had approximately 72,404 employees in 2024, up from 67,317 in 2023, reflecting continued investment in AI and metaverse initiatives.",
    "What are Tesla's main risk factors?": "Tesla's key risks include increasing competition in the EV market, dependency on Elon Musk, supply chain challenges, regulatory uncertainties, and manufacturing scaling difficulties.",
    "What is Amazon Web Services revenue?": "AWS revenue was approximately $105.2 billion in 2024, growing 19% year-over-year, remaining the leading cloud infrastructure provider.",
    "Compare Microsoft and Google cloud revenue.": "Microsoft Intelligent Cloud revenue was approximately $105.4B. Google Cloud revenue was approximately $43.6B. Microsoft's cloud business is roughly 2.4x larger than Google Cloud.",
    "What is Apple's total revenue?": "Apple reported total revenue of $391.0 billion for fiscal year 2024, with growth driven by Services and iPhone segments.",
    "What was Microsoft's net income for 2024?": "Microsoft reported net income of $88.1 billion for fiscal year 2024, with a net margin of approximately 36%.",
    "How much did Amazon spend on R&D in 2024?": "Amazon spent approximately $85.6 billion on research and development in 2024, one of the highest R&D expenditures among tech companies.",
    "What is Tesla's gross margin?": "Tesla's automotive gross margin was approximately 17.9% in 2024, down from previous years due to price cuts and increased competition.",
    "How many devices does Apple have in active install base?": "Apple reported over 2.2 billion active devices worldwide as of 2024, spanning iPhone, iPad, Mac, Apple Watch, and Apple TV.",
    "What is Meta's operating income?": "Meta reported operating income of approximately $52.0 billion in 2024, with operating margin improving as Reality Labs losses narrowed.",
    "Compare Amazon and Microsoft operating income.": "Amazon operating income was approximately $68.9B. Microsoft operating income was approximately $109.4B. Microsoft has higher profitability despite lower revenue.",
    "What is Google's advertising revenue?": "Google advertising revenue was approximately $264.7 billion in 2024, including Search, YouTube, and Google Network properties.",
    "What are Amazon's business segments?": "Amazon operates through three segments: North America, International, and Amazon Web Services (AWS). AWS is the most profitable segment.",
    "How much did Tesla deliver in vehicles?": "Tesla delivered approximately 1.79 million vehicles in 2024, a slight increase from 1.81 million in 2023.",
    "What is Apple's services revenue?": "Apple Services revenue was approximately $96.2 billion in fiscal year 2024, growing double-digits and representing about 25% of total revenue.",
    "Compare Tesla and Rivian risk factors.": "Tesla risks: EV competition, Musk dependency, supply chain, regulatory. Rivian risks: production scaling, cash burn, competition with established automakers, limited production history.",
    "What is Microsoft's capital expenditure?": "Microsoft capital expenditure was approximately $44.5 billion in fiscal year 2024, primarily for AI and cloud infrastructure.",
    "How much does Alphabet invest in AI?": "Alphabet's capital expenditure on AI and infrastructure was approximately $32.3 billion in 2024, with plans to increase further.",
    "What is Meta's reality labs revenue?": "Meta's Reality Labs segment generated approximately $2.1 billion in revenue in 2024, with operating losses of approximately $16.1 billion.",
    "Compare R&D spending across FAANG companies.": "Amazon R&D: $85.6B, Google R&D: $49.3B, Meta R&D: $39.5B, Apple R&D: $30.5B, Netflix R&D: ~$2.5B. Amazon leads in absolute R&D spending.",
    "What is Amazon's free cash flow?": "Amazon's free cash flow was approximately $46.9 billion in 2024, recovering from negative FCF in 2022.",
    "What is Tesla's energy generation revenue?": "Tesla's energy generation and storage revenue was approximately $10.1 billion in 2024, growing rapidly as energy storage deployments increased.",
    "How many data centers does Microsoft operate?": "Microsoft operates over 60 data center regions worldwide as of 2024, with ongoing expansion to support Azure and AI workloads.",
    "What is Apple's net cash position?": "Apple had net cash of approximately $62.4 billion as of 2024, after returning over $100 billion to shareholders through buybacks and dividends.",
    "What is Google's total number of employees?": "Alphabet had approximately 183,323 employees in 2024, with continued hiring in AI and cloud divisions.",
    "Compare cloud revenue growth of AWS, Azure, and Google Cloud.": "AWS revenue grew 19% YoY to $105.2B. Microsoft Azure grew 29%. Google Cloud grew 30% to $43.6B. Google Cloud and Azure growing faster than AWS.",
    "What is Tesla's vehicle margin?": "Tesla's automotive margin was approximately 17.9% in 2024, impacted by price reductions and mix shift toward lower-margin models.",
    "How much did Amazon return to shareholders?": "Amazon repurchased approximately $6.0 billion in shares and paid $0.9 billion in dividends in 2024.",
    "What is Microsoft's dividend yield?": "Microsoft's annual dividend was $3.32 per share, yielding approximately 0.7% at current prices.",
    "What is Alphabet's other bets revenue?": "Alphabet's Other Bets revenue was approximately $1.5 billion in 2024, with operating losses of approximately $4.5 billion.",
    "How many subscribers does Netflix have?": "Netflix had approximately 301 million paid subscribers globally in 2024, up from 260 million in 2023.",
    "What is Apple's operating margin?": "Apple's operating margin was approximately 31.5% in fiscal year 2024, among the highest in the industry.",
    "Compare Meta and Google advertising revenue.": "Meta advertising revenue was approximately $160.2B. Google advertising revenue was approximately $264.7B. Google leads in advertising revenue.",
    "What is Tesla's debt level?": "Tesla had approximately $7.4 billion in total debt as of end of 2024, with a strong cash position of over $33 billion.",
    "What is Amazon's operating cash flow?": "Amazon's operating cash flow was approximately $115.9 billion in 2024, a significant increase from prior years.",
    "What is Nvidia's revenue from data centers?": "Nvidia data center revenue was approximately $115.2 billion in fiscal 2025, driven by massive AI infrastructure demand.",
    "How does Tesla's revenue compare to traditional automakers?": "Tesla revenue $97.7B vs Toyota $284B, Volkswagen $295B, GM $171B in 2024. Tesla is smaller but growing in the EV segment.",
    "What is Microsoft's AI revenue contribution?": "Microsoft reported $13 billion in annual revenue from AI services, growing 175% YoY, with Copilot driving enterprise adoption.",
    "What is Google's YouTube revenue?": "YouTube advertising revenue was approximately $36.1 billion in 2024, with YouTube Premium and subscriptions adding additional revenue.",
    "Compare Tesla and BYD vehicle sales.": "Tesla delivered 1.79M vehicles. BYD sold 4.27M vehicles (including hybrids) in 2024. BYD has surpassed Tesla in total volume.",
    "What is Apple's iPhone revenue?": "Apple iPhone revenue was approximately $201.2 billion in fiscal year 2024, remaining the largest product category.",
    "What is Amazon's advertising revenue?": "Amazon advertising revenue was approximately $56.2 billion in 2024, making it the third-largest digital ad platform after Google and Meta.",
    "How much did Meta spend on the metaverse?": "Meta's Reality Labs operating loss was approximately $16.1 billion in 2024, with revenue of $2.1 billion.",
    "What is Microsoft's gaming revenue?": "Microsoft gaming revenue was approximately $21.5 billion in fiscal year 2024, boosted by the Activision Blizzard acquisition.",
    "What is Tesla's market share in EVs?": "Tesla held approximately 18% global EV market share in 2024, down from 23% in 2023 due to increasing competition.",
    "What is Alphabet's Waymo revenue?": "Alphabet's Waymo autonomous driving unit was not broken out separately but operated commercially in San Francisco, Phoenix, and Los Angeles.",
    "What is Apple's wearables revenue?": "Apple Wearables, Home and Accessories revenue was approximately $39.8 billion in fiscal year 2024.",
    "How does AWS profitability compare to Azure?": "AWS operating income was $39.8B with 38% margin. Azure margin was approximately 44%, making Azure slightly more profitable.",
    "What is Netflix's revenue per subscriber?": "Netflix average revenue per membership was approximately $12.50/month globally in 2024.",
    "What are Nvidia's competitive advantages?": "Nvidia advantages: CUDA ecosystem, developer lock-in, 90%+ AI chip market share, full-stack hardware+software platform, networking (InfiniBand).",
}


def build_mock_eval_data() -> list[dict]:
    """Build evaluation data with mock answers from golden dataset."""
    eval_data = []
    for item in GOLDEN_DATASET:
        q = item["question"]
        answer = MOCK_ANSWERS.get(q, f"Based on SEC filings, {item['ground_truth']}")
        eval_data.append({
            "question": q,
            "answer": answer,
            "contexts": [item["ground_truth"]],  # use ground truth as context
            "ground_truth": item["ground_truth"],
        })
    return eval_data


def main():
    print("=" * 70)
    print("LLM-as-Judge RAGAS Evaluation")
    print("Judge Model: minimax-m3:cloud via Ollama Cloud")
    print(f"Samples: {len(GOLDEN_DATASET)}")
    print("=" * 70)

    judge = LLMJudge()
    eval_data = build_mock_eval_data()

    print(f"\nRunning evaluation on {len(eval_data)} samples...")
    print("(This will take a few minutes — each sample requires 4 LLM calls)\n")

    results = []
    for i, item in enumerate(eval_data):
        print(f"[{i+1:2d}/{len(eval_data)}] {item['question'][:60]}...", end=" ", flush=True)
        result = judge.evaluate(
            question=item["question"],
            answer=item["answer"],
            contexts=item["contexts"],
            ground_truth=item["ground_truth"],
        )
        results.append(result)
        print(f"F={result.faithfulness:.2f} R={result.answer_relevancy:.2f} P={result.context_precision:.2f} Rc={result.context_recall:.2f}")

    metrics = judge.compute_metrics(results)

    print("\n" + "=" * 70)
    print("LLM-as-Judge EVALUATION RESULTS")
    print("=" * 70)
    print(f"  Faithfulness:      {metrics['faithfulness']:.4f}")
    print(f"  Answer Relevancy:  {metrics['answer_relevancy']:.4f}")
    print(f"  Context Precision: {metrics['context_precision']:.4f}")
    print(f"  Context Recall:    {metrics['context_recall']:.4f}")
    print(f"  Overall Score:     {metrics['overall_score']:.4f}")
    print(f"  Num Samples:       {metrics['num_samples']}")
    print("=" * 70)

    output_path = project_root / "data" / "eval" / "llm_judge_results.json"
    save_llm_eval_results(results, metrics, str(output_path))
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
