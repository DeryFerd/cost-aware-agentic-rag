"""Golden set of labeled Q&A pairs for evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, asdict

from src.config import settings


@dataclass
class GoldenPair:
    id: str
    query: str
    expected_answer: str
    category: str  # "factual", "comparison", "analysis", "aggregation"
    difficulty: str  # "easy", "medium", "hard"
    companies: list[str]
    source_docs: list[str]


# Default golden set for SEC 10-K evaluation
DEFAULT_GOLDEN_SET: list[GoldenPair] = [
    GoldenPair(
        id="factual_001",
        query="What was Microsoft's total revenue in fiscal year 2024?",
        expected_answer="Microsoft reported total revenue of $245.1 billion for fiscal year 2024.",
        category="factual",
        difficulty="easy",
        companies=["MSFT"],
        source_docs=["MSFT_2024_10K"],
    ),
    GoldenPair(
        id="comparison_001",
        query="Compare the revenue growth rates of Amazon and Microsoft over the last 3 years.",
        expected_answer="Comparison of revenue growth: MSFT grew from $198B to $245B (23.7% over 3 years), AMZN grew from $469B to $574B (22.4% over 3 years).",
        category="comparison",
        difficulty="medium",
        companies=["AMZN", "MSFT"],
        source_docs=["AMZN_2024_10K", "MSFT_2024_10K"],
    ),
    GoldenPair(
        id="analysis_001",
        query="What are the main risk factors mentioned in Tesla's 10-K filing?",
        expected_answer="Tesla's key risks include: manufacturing scalability, competition in EV market, regulatory changes, supply chain dependencies, and macroeconomic conditions.",
        category="analysis",
        difficulty="medium",
        companies=["TSLA"],
        source_docs=["TSLA_2024_10K"],
    ),
    GoldenPair(
        id="factual_002",
        query="How many employees does Alphabet have?",
        expected_answer="Alphabet reported approximately 183,323 employees as of December 2024.",
        category="factual",
        difficulty="easy",
        companies=["GOOG"],
        source_docs=["GOOG_2024_10K"],
    ),
    GoldenPair(
        id="aggregation_001",
        query="What is the combined market capitalization of FAANG companies based on their latest 10-K filings?",
        expected_answer="Aggregated market cap data from latest filings requires cross-referencing multiple 10-K reports.",
        category="aggregation",
        difficulty="hard",
        companies=["META", "AMZN", "AAPL", "NFLX", "GOOG"],
        source_docs=["META_2024_10K", "AMZN_2024_10K", "GOOG_2024_10K"],
    ),
]


class GoldenSetManager:
    """Manage the golden set of evaluation pairs."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.eval_dir / "golden_set.json"

    def load(self) -> list[GoldenPair]:
        if not self.path.exists():
            return DEFAULT_GOLDEN_SET

        with open(self.path) as f:
            data = json.load(f)
        return [GoldenPair(**item) for item in data]

    def save(self, pairs: list[GoldenPair]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump([asdict(p) for p in pairs], f, indent=2)

    def filter(
        self,
        category: str | None = None,
        difficulty: str | None = None,
        companies: list[str] | None = None,
    ) -> list[GoldenPair]:
        pairs = self.load()
        if category:
            pairs = [p for p in pairs if p.category == category]
        if difficulty:
            pairs = [p for p in pairs if p.difficulty == difficulty]
        if companies:
            pairs = [p for p in pairs if any(c in p.companies for c in companies)]
        return pairs
