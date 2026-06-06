"""BM25 sparse retrieval index."""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from src.config import settings


class BM25Index:
    """BM25-based sparse retrieval with persistence."""

    def __init__(self) -> None:
        self.corpus: list[str] = []
        self.metadata: list[dict] = []
        self.bm25: BM25Okapi | None = None

    def _tokenize(self, text: str) -> list[str]:
        """Simple whitespace + lowercasing tokenizer."""
        return text.lower().split()

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
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "corpus": self.corpus,
                    "metadata": self.metadata,
                },
                f,
            )

    def load(self, path: Path | None = None) -> bool:
        """Load index from disk. Returns False if not found."""
        path = path or settings.bm25_path
        if not path.exists():
            return False

        with open(path, "rb") as f:
            data = pickle.load(f)  # noqa: S301

        self.corpus = data["corpus"]
        self.metadata = data["metadata"]
        tokenized = [self._tokenize(doc) for doc in self.corpus]
        self.bm25 = BM25Okapi(tokenized)
        return True

    def count(self) -> int:
        return len(self.corpus)
