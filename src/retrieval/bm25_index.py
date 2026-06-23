"""BM25 sparse retrieval index with proper tokenization."""

from __future__ import annotations

import re
from pathlib import Path

import joblib
import numpy as np
from rank_bm25 import BM25Okapi

from src.config import settings

# English stopwords
STOP_WORDS = frozenset({
    "a", "an", "the", "in", "on", "at", "for", "to", "of", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "shall", "can", "need", "dare", "ought", "used", "with", "from", "by",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "about", "it", "its", "this", "that",
    "these", "those", "what", "which", "who", "whom", "i", "me", "my",
    "we", "our", "you", "your", "he", "him", "his", "she", "her", "they",
    "them", "their", "if", "while", "also",
})

# Simple stemmer (Porter-like suffix rules)
_SUFFIX_RULES = [
    ("ational", "ate"), ("tional", "tion"), ("enci", "ence"),
    ("anci", "ance"), ("izer", "ize"), ("ously", "ous"),
    ("iveness", "ive"), ("fulness", "ful"), ("ousness", "ous"),
    ("aliti", "al"), ("iviti", "ive"), ("biliti", "ble"),
    ("ling", ""), ("ement", ""), ("ment", ""),
    ("ence", ""), ("ance", ""), ("able", ""), ("ible", ""),
    ("tion", "t"), ("sion", "s"),
    ("ies", "i"), ("ive", ""), ("ful", ""),
    ("ness", ""), ("ly", ""), ("er", ""), ("ed", ""),
    ("ing", ""), ("ss", "ss"), ("s", ""),
]


def _simple_stem(word: str) -> str:
    """Apply simple suffix-stripping stemmer."""
    if len(word) <= 3 or word.endswith(("ss", "us", "is")):
        return word
    for suffix, replacement in _SUFFIX_RULES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)] + replacement
    return word


class BM25Index:
    """BM25-based sparse retrieval with persistence and proper tokenization."""

    def __init__(self) -> None:
        self.corpus: list[str] = []
        self.metadata: list[dict] = []
        self.bm25: BM25Okapi | None = None

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize with lowercasing, stopword removal, and stemming."""
        # Lowercase and split on non-alphanumeric
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        # Remove stopwords and apply stemming
        return [_simple_stem(t) for t in tokens if t not in STOP_WORDS and len(t) > 1]

    def add_documents(self, chunks: list[dict]) -> int:
        """Add chunks to the BM25 index."""
        for chunk in chunks:
            self.corpus.append(chunk["text"])
            self.metadata.append(chunk.get("metadata", {}))

        tokenized = [self._tokenize(doc) for doc in self.corpus]
        self.bm25 = BM25Okapi(tokenized)
        return len(chunks)

    def search(self, query: str, top_k: int = settings.top_k) -> list[dict]:
        """Search using BM25 scoring."""
        if self.bm25 is None:
            return []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append(
                    {
                        "text": self.corpus[idx],
                        "score": float(scores[idx]),
                        "metadata": self.metadata[idx],
                    }
                )
        return results

    def save(self, path: Path | None = None) -> None:
        """Persist index to disk."""
        path = path or settings.bm25_path
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "corpus": self.corpus,
                "metadata": self.metadata,
            },
            path,
        )

    def load(self, path: Path | None = None) -> bool:
        """Load index from disk. Returns False if not found."""
        path = path or settings.bm25_path
        if not path.exists():
            return False

        data = joblib.load(path)

        self.corpus = data["corpus"]
        self.metadata = data["metadata"]
        tokenized = [self._tokenize(doc) for doc in self.corpus]
        self.bm25 = BM25Okapi(tokenized)
        return True

    def count(self) -> int:
        return len(self.corpus)
