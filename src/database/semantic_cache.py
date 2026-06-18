"""Semantic caching for queries using bge-small-en-v1.5 embeddings."""

from __future__ import annotations

import json
import time
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import settings

_TTL_SECONDS = 24 * 60 * 60  # 24 hours
_MAX_ENTRIES = 1000
_SIMILARITY_THRESHOLD = 0.92
_CACHE_PATH = settings.data_dir / "cache" / "semantic_cache.json"

_embedding_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class SemanticCache:
    """JSON-backed semantic cache for query responses."""

    def __init__(self) -> None:
        self._cache_path = _CACHE_PATH
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict[str, Any]] = []
        self._hits = 0
        self._misses = 0
        self._load()

    # ── persistence ──────────────────────────────────────────────

    def _load(self) -> None:
        if self._cache_path.exists():
            try:
                with open(self._cache_path, encoding="utf-8") as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._entries = []

    def _save(self) -> None:
        # Evict expired entries before writing
        now = time.time()
        self._entries = [
            e for e in self._entries
            if now - e.get("timestamp", 0) < _TTL_SECONDS
        ]
        # Enforce max size (drop oldest first)
        if len(self._entries) > _MAX_ENTRIES:
            self._entries = sorted(
                self._entries, key=lambda e: e.get("timestamp", 0)
            )[-_MAX_ENTRIES:]
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, ensure_ascii=False, indent=2)

    # ── public API ───────────────────────────────────────────────

    def get(self, query: str) -> dict | None:
        """Return cached response if a semantically similar query exists."""
        now = time.time()

        # 1. Try semantic similarity lookup
        try:
            model = _get_model()
            query_emb = model.encode([query], show_progress_bar=False)[0]

            best_score = -1.0
            best_entry: dict[str, Any] | None = None

            for entry in self._entries:
                if now - entry.get("timestamp", 0) >= _TTL_SECONDS:
                    continue
                cached_emb = np.array(entry["embedding"])
                sim = _cosine_similarity(query_emb, cached_emb)
                if sim > best_score:
                    best_score = sim
                    best_entry = entry

            if best_entry is not None and best_score >= _SIMILARITY_THRESHOLD:
                self._hits += 1
                return best_entry["response"]
        except Exception:
            # Fall through to exact match
            pass

        # 2. Exact-match fallback (hash-based key)
        for entry in self._entries:
            if now - entry.get("timestamp", 0) >= _TTL_SECONDS:
                continue
            if entry.get("query") == query:
                self._hits += 1
                return entry["response"]

        self._misses += 1
        return None

    def set(self, query: str, response: dict) -> None:
        """Cache a query-response pair."""
        try:
            model = _get_model()
            embedding = model.encode([query], show_progress_bar=False)[0].tolist()
        except Exception:
            embedding = []

        self._entries.append({
            "query": query,
            "embedding": embedding,
            "response": response,
            "timestamp": time.time(),
        })

        # Enforce max size immediately
        if len(self._entries) > _MAX_ENTRIES:
            self._entries = sorted(
                self._entries, key=lambda e: e.get("timestamp", 0)
            )[-_MAX_ENTRIES:]

        self._save()

    def clear(self) -> None:
        """Clear all cache entries."""
        self._entries = []
        self._hits = 0
        self._misses = 0
        self._save()

    def stats(self) -> dict:
        """Return hit/miss rates and entry count."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total else 0.0,
            "entries": len(self._entries),
            "max_entries": _MAX_ENTRIES,
            "ttl_seconds": _TTL_SECONDS,
        }


def get_semantic_cache() -> SemanticCache:
    """Return a module-level singleton :class:`SemanticCache`."""
    return _cache


_cache = SemanticCache()
