"""Cost-aware routing classifier for model selection.

Instead of keyword matching, this module provides:
1. A trained classifier for query complexity
2. Cost-aware routing that balances quality vs cost
3. Fallback to LLM-based classification when classifier is unavailable
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """Result of routing classification."""
    complexity: str  # "simple" or "complex"
    confidence: float
    model: str
    cost_estimate: float
    method: str  # "classifier" or "llm"


class QueryClassifier:
    """Trained classifier for query complexity."""

    def __init__(self):
        self.pipeline: Optional[Pipeline] = None
        self._load_model()

    def _load_model(self):
        """Load trained model if available."""
        model_path = settings.project_root / "data" / "models" / "query_classifier.pkl"
        if model_path.exists():
            try:
                with open(model_path, "rb") as f:
                    self.pipeline = pickle.load(f)
                logger.info(f"Loaded query classifier from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load classifier: {e}")

    def train(self, queries: list[str], labels: list[str]):
        """Train the classifier on labeled data."""
        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                max_features=1000,
                ngram_range=(1, 2),
                stop_words="english",
            )),
            ("classifier", LogisticRegression(
                max_iter=1000,
                C=1.0,
                class_weight="balanced",
            )),
        ])

        self.pipeline.fit(queries, labels)

        # Save model
        model_dir = settings.project_root / "data" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / "query_classifier.pkl"

        with open(model_path, "wb") as f:
            pickle.dump(self.pipeline, f)

        logger.info(f"Trained and saved classifier to {model_path}")

    def predict(self, query: str) -> tuple[str, float]:
        """Predict complexity and confidence."""
        if self.pipeline is None:
            return "simple", 0.5

        prediction = self.pipeline.predict([query])[0]
        proba = self.pipeline.predict_proba([query])[0]
        confidence = float(max(proba))

        return prediction, confidence


# ── Training Data ─────────────────────────────────────────────────

TRAINING_DATA = [
    # Simple queries (factual lookup)
    ("What is Microsoft's revenue?", "simple"),
    ("How many employees does Amazon have?", "simple"),
    ("What is Tesla's stock ticker?", "simple"),
    ("When was Apple founded?", "simple"),
    ("What is Google's main product?", "simple"),
    ("Show me Meta's 2024 revenue", "simple"),
    ("What is NVDA?", "simple"),
    ("List Amazon's business segments", "simple"),
    ("What year did Tesla IPO?", "simple"),
    ("Who is the CEO of Microsoft?", "simple"),
    ("What is Alphabet's ticker symbol?", "simple"),
    ("How much revenue did Apple make in 2024?", "simple"),
    ("What is Nvidia's main business?", "simple"),
    ("Show me Tesla's employee count", "simple"),
    ("What is Microsoft's cloud revenue?", "simple"),

    # Complex queries (comparison, analysis)
    ("Compare Microsoft and Amazon revenue growth", "complex"),
    ("Analyze Tesla's risk factors across years", "complex"),
    ("What are the implications of AI on tech companies?", "complex"),
    ("Forecast Google's revenue based on trends", "complex"),
    ("Compare employee growth across FAANG companies", "complex"),
    ("Analyze the competitive landscape of cloud providers", "complex"),
    ("What are the main risk factors for Tesla vs Rivian?", "complex"),
    ("Compare R&D spending across tech giants", "complex"),
    ("Analyze Meta's metaverse investment returns", "complex"),
    ("What is the correlation between AI investment and revenue?", "complex"),
    ("Compare Microsoft Azure vs AWS market share", "complex"),
    ("Analyze supply chain risks for Apple", "complex"),
    ("Compare Tesla's energy business to competitors", "complex"),
    ("What are the regulatory risks for Google?", "complex"),
    ("Analyze Nvidia's competitive moat in AI chips", "complex"),
]


def train_classifier() -> QueryClassifier:
    """Train the query classifier on labeled data."""
    classifier = QueryClassifier()
    queries, labels = zip(*TRAINING_DATA)
    classifier.train(list(queries), list(labels))
    return classifier


# ── Cost-Aware Router ─────────────────────────────────────────────

class CostAwareRouter:
    """Routes queries to appropriate models based on complexity and cost."""

    def __init__(self):
        self.classifier = QueryClassifier()
        self._cost_per_token = {
            settings.ollama_simple_model: {"input": 0.05, "output": 0.10},   # lightweight
            settings.ollama_complex_model: {"input": 0.25, "output": 0.50},  # heavy
        }

    def route(self, query: str, budget: float = 0.05) -> RoutingResult:
        """Route query to appropriate model."""
        # Try classifier first
        complexity, confidence = self.classifier.predict(query)
        method = "classifier"

        # Fall back to LLM if confidence is low
        if confidence < 0.6:
            complexity = self._llm_classify(query)
            method = "llm"
            confidence = 0.7

        # Select model based on complexity
        model = (
            settings.ollama_complex_model
            if complexity == "complex"
            else settings.ollama_simple_model
        )

        # Estimate cost
        cost_estimate = self._estimate_cost(query, model)

        return RoutingResult(
            complexity=complexity,
            confidence=confidence,
            model=model,
            cost_estimate=cost_estimate,
            method=method,
        )

    def _llm_classify(self, query: str) -> str:
        """Fallback LLM classification."""
        from src.generation.llm_client import OllamaClient

        llm = OllamaClient()
        return llm.classify_complexity(query)

    def _estimate_cost(self, query: str, model: str) -> float:
        """Estimate cost for query."""
        # Rough estimate: 1 token per 4 chars
        estimated_tokens = len(query) / 4
        costs = self._cost_per_token.get(model, {"input": 0.0, "output": 0.0})
        return (estimated_tokens * costs["input"]) / 1_000_000


# ── Public API ────────────────────────────────────────────────────

def get_cost_aware_router() -> CostAwareRouter:
    """Get a cost-aware router instance."""
    return CostAwareRouter()
