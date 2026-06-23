"""Cost-aware routing classifier for model selection.

Instead of keyword matching, this module provides:
1. A trained classifier for query complexity
2. Cost-aware routing that balances quality vs cost
3. Fallback to LLM-based classification when classifier is unavailable
4. Metrics reporting with train/test split and cross-validation
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline

from src.config import settings

logger = logging.getLogger(__name__)

# ── Training Data File ─────────────────────────────────────────────
TRAINING_DATA_PATH = settings.project_root / "data" / "training" / "routing_data.json"


@dataclass
class RoutingResult:
    """Result of routing classification."""
    complexity: str  # "simple" or "complex"
    confidence: float
    model: str
    cost_estimate: float
    method: str  # "classifier" or "llm"


@dataclass
class TrainingMetrics:
    """Metrics from classifier training."""
    accuracy: float
    precision_simple: float
    precision_complex: float
    recall_simple: float
    recall_complex: float
    f1_simple: float
    f1_complex: float
    f1_macro: float
    confusion_matrix: list[list[int]]
    classification_report: str
    cv_mean: float
    cv_std: float
    train_size: int
    test_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "accuracy": self.accuracy,
            "precision": {"simple": self.precision_simple, "complex": self.precision_complex},
            "recall": {"simple": self.recall_simple, "complex": self.recall_complex},
            "f1": {"simple": self.f1_simple, "complex": self.f1_complex, "macro": self.f1_macro},
            "confusion_matrix": self.confusion_matrix,
            "cv_mean": self.cv_mean,
            "cv_std": self.cv_std,
            "train_size": self.train_size,
            "test_size": self.test_size,
        }


class QueryClassifier:
    """Trained classifier for query complexity."""

    def __init__(self):
        self.pipeline: Pipeline | None = None
        self._load_model()

    def _load_model(self):
        """Load trained model if available, with hash verification."""
        model_path = settings.project_root / "data" / "models" / "query_classifier.pkl"
        hash_path = model_path.with_suffix(".pkl.sha256")
        if model_path.exists():
            try:
                # Verify hash if hash file exists
                if hash_path.exists():
                    expected_hash = hash_path.read_text().strip()
                    actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
                    if actual_hash != expected_hash:
                        logger.warning(
                            f"Classifier hash mismatch! Expected {expected_hash[:16]}..., "
                            f"got {actual_hash[:16]}... — refusing to load"
                        )
                        return

                self.pipeline = joblib.load(model_path)
                logger.info(f"Loaded query classifier from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load classifier: {e}")

    def train(self, queries: list[str], labels: list[str]) -> None:
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

        # Save model with hash verification
        model_dir = settings.project_root / "data" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / "query_classifier.pkl"
        hash_path = model_path.with_suffix(".pkl.sha256")

        joblib.dump(self.pipeline, model_path)

        # Save SHA-256 hash for integrity verification
        model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
        hash_path.write_text(model_hash)

        logger.info(f"Trained and saved classifier to {model_path} (hash: {model_hash[:16]}...)")

    def predict(self, query: str) -> tuple[str, float]:
        """Predict complexity and confidence."""
        if self.pipeline is None:
            return "simple", 0.5

        prediction = self.pipeline.predict([query])[0]
        proba = self.pipeline.predict_proba([query])[0]
        confidence = float(max(proba))

        return prediction, confidence


# ── Training Data Loading ──────────────────────────────────────────

def _load_training_data() -> list[tuple[str, str]]:
    """Load training data from JSON file with inline fallback."""
    if TRAINING_DATA_PATH.exists():
        try:
            with open(TRAINING_DATA_PATH, encoding="utf-8") as f:
                data = json.load(f)
            examples = [(ex["query"], ex["complexity"]) for ex in data["examples"]]
            logger.info(f"Loaded {len(examples)} training examples from {TRAINING_DATA_PATH}")
            return examples
        except Exception as e:
            logger.warning(f"Failed to load training data from JSON: {e}. Using built-in fallback.")

    # Fallback: minimal built-in data if JSON file is missing
    return _FALLBACK_TRAINING_DATA


_FALLBACK_TRAINING_DATA: list[tuple[str, str]] = [
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

# Backward-compatible alias for tests
TRAINING_DATA = _FALLBACK_TRAINING_DATA


# ── Training with Metrics ──────────────────────────────────────────

def train_with_metrics(
    test_size: float = 0.2,
    cv_folds: int = 5,
    random_state: int = 42,
) -> tuple[QueryClassifier, TrainingMetrics]:
    """Train classifier with full metrics reporting.

    Args:
        test_size: Fraction of data to hold out for testing.
        cv_folds: Number of cross-validation folds.
        random_state: Random seed for reproducibility.

    Returns:
        Tuple of (trained classifier, training metrics).
    """
    data = _load_training_data()
    queries, labels = zip(*data, strict=False)

    # Stratified train/test split
    x_train, x_test, y_train, y_test = train_test_split(
        list(queries),
        list(labels),
        test_size=test_size,
        random_state=random_state,
        stratify=list(labels),
    )

    # Build and train pipeline
    pipeline = Pipeline([
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

    pipeline.fit(x_train, y_train)

    # Predictions on test set
    y_pred = pipeline.predict(x_test)

    # Core metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision_simple = precision_score(y_test, y_pred, pos_label="simple", zero_division=0)
    precision_complex = precision_score(y_test, y_pred, pos_label="complex", zero_division=0)
    recall_simple = recall_score(y_test, y_pred, pos_label="simple", zero_division=0)
    recall_complex = recall_score(y_test, y_pred, pos_label="complex", zero_division=0)
    f1_simple = f1_score(y_test, y_pred, pos_label="simple", zero_division=0)
    f1_complex = f1_score(y_test, y_pred, pos_label="complex", zero_division=0)
    f1_macro = f1_score(y_test, y_pred, average="macro", zero_division=0)

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred, labels=["simple", "complex"])
    cm_list = cm.tolist()

    # Classification report
    report_str = classification_report(y_test, y_pred, zero_division=0)

    # Cross-validation on full dataset
    full_pipeline = Pipeline([
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

    skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    cv_scores = cross_val_score(full_pipeline, list(queries), list(labels), cv=skf, scoring="accuracy")

    metrics = TrainingMetrics(
        accuracy=accuracy,
        precision_simple=precision_simple,
        precision_complex=precision_complex,
        recall_simple=recall_simple,
        recall_complex=recall_complex,
        f1_simple=f1_simple,
        f1_complex=f1_complex,
        f1_macro=f1_macro,
        confusion_matrix=cm_list,
        classification_report=report_str,
        cv_mean=float(cv_scores.mean()),
        cv_std=float(cv_scores.std()),
        train_size=len(x_train),
        test_size=len(x_test),
    )

    # Build classifier with the trained pipeline
    classifier = QueryClassifier()
    classifier.pipeline = pipeline

    # Save model with hash verification
    model_dir = settings.project_root / "data" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "query_classifier.pkl"
    hash_path = model_path.with_suffix(".pkl.sha256")

    joblib.dump(pipeline, model_path)

    # Save SHA-256 hash for integrity verification
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    hash_path.write_text(model_hash)

    logger.info(f"Trained classifier with {len(queries)} examples, saved to {model_path}")
    logger.info(f"Test accuracy: {accuracy:.3f} | CV: {cv_scores.mean():.3f} +/- {cv_scores.std():.3f}")
    logger.info(f"\n{report_str}")

    return classifier, metrics


def print_metrics(metrics: TrainingMetrics) -> None:
    """Pretty-print training metrics."""
    print("\n" + "=" * 60)
    print("CLASSIFIER TRAINING METRICS")
    print("=" * 60)
    print(f"  Train size:       {metrics.train_size}")
    print(f"  Test size:        {metrics.test_size}")
    print(f"  Accuracy:         {metrics.accuracy:.3f}")
    print(f"  F1 (macro):       {metrics.f1_macro:.3f}")
    print("-" * 60)
    print("  Per-class metrics:")
    print(f"    Simple  - Precision: {metrics.precision_simple:.3f}  Recall: {metrics.recall_simple:.3f}  F1: {metrics.f1_simple:.3f}")
    print(f"    Complex - Precision: {metrics.precision_complex:.3f}  Recall: {metrics.recall_complex:.3f}  F1: {metrics.f1_complex:.3f}")
    print("-" * 60)
    print(f"  Cross-val score:  {metrics.cv_mean:.3f} +/- {metrics.cv_std:.3f}")
    print("-" * 60)
    print("  Confusion Matrix (rows=true, cols=pred):")
    print("              Pred Simple  Pred Complex")
    print(f"    True Simple   {metrics.confusion_matrix[0][0]:>6}      {metrics.confusion_matrix[0][1]:>6}")
    print(f"    True Complex  {metrics.confusion_matrix[1][0]:>6}      {metrics.confusion_matrix[1][1]:>6}")
    print("-" * 60)
    print("  Classification Report:")
    print(metrics.classification_report)
    print("=" * 60)


# ── Legacy Training API ────────────────────────────────────────────

def train_classifier() -> QueryClassifier:
    """Train the query classifier on labeled data (backward-compatible)."""
    classifier = QueryClassifier()
    data = _load_training_data()
    queries, labels = zip(*data, strict=False)
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
