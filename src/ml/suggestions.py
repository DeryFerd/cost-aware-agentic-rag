"""Query suggestion based on historical queries and document content."""

from __future__ import annotations

import re
from collections import Counter

from src.config import settings
from src.generation.cost_tracker import CostTracker


class QuerySuggestion:
    """Generate query suggestions based on history and documents."""

    def __init__(self) -> None:
        self.tracker = CostTracker()
        self.suggestions_file = settings.data_dir / "suggestions.json"

    def get_suggestions(self, limit: int = 5) -> list[dict]:
        """Get query suggestions based on popular patterns."""
        history = self.tracker.load_history()

        # Extract common query patterns
        patterns = self._extract_patterns(history)

        # Get document-based suggestions
        doc_suggestions = self._get_document_suggestions()

        # Combine and deduplicate
        all_suggestions = []

        # Add pattern-based suggestions
        for pattern in patterns[:limit]:
            all_suggestions.append({
                "query": pattern["query"],
                "source": "popular",
                "count": pattern["count"],
            })

        # Add document-based suggestions
        for suggestion in doc_suggestions[:limit]:
            if len(all_suggestions) >= limit:
                break
            all_suggestions.append({
                "query": suggestion,
                "source": "document",
                "count": 0,
            })

        # Add default suggestions if not enough
        defaults = self._get_default_suggestions()
        for suggestion in defaults:
            if len(all_suggestions) >= limit:
                break
            all_suggestions.append({
                "query": suggestion,
                "source": "default",
                "count": 0,
            })

        return all_suggestions[:limit]

    def get_related_queries(self, query: str, limit: int = 3) -> list[str]:
        """Get queries related to the input query."""
        history = self.tracker.load_history()
        query_lower = query.lower()

        # Find similar queries from history
        related = []
        for record in history:
            if record.query.lower() != query_lower:
                similarity = self._calculate_similarity(query_lower, record.query.lower())
                if similarity > 0.3:
                    related.append(record.query)

        # Deduplicate while preserving order
        seen = set()
        unique_related = []
        for q in related:
            if q not in seen:
                seen.add(q)
                unique_related.append(q)

        return unique_related[:limit]

    def _extract_patterns(self, history: list) -> list[dict]:
        """Extract common query patterns from history."""
        if not history:
            return []

        # Group queries by similarity
        query_counts = Counter()
        for record in history:
            # Normalize query
            normalized = self._normalize_query(record.query)
            query_counts[normalized] += 1

        # Return most common patterns
        patterns = []
        for query, count in query_counts.most_common(10):
            patterns.append({"query": query, "count": count})

        return patterns

    def _normalize_query(self, query: str) -> str:
        """Normalize query for pattern matching."""
        # Remove company names and years for pattern matching
        companies = (
            r'\b(MSFT|AMZN|TSLA|GOOG|META|AAPL|NVDA|'
            r'Microsoft|Amazon|Tesla|Google|Meta|Apple|NVIDIA)\b'
        )
        normalized = re.sub(companies, '[COMPANY]', query, flags=re.IGNORECASE)
        normalized = re.sub(r'\b(202[0-9])\b', '[YEAR]', normalized)
        return normalized.strip()

    def _calculate_similarity(self, query1: str, query2: str) -> float:
        """Calculate simple word overlap similarity."""
        words1 = set(query1.split())
        words2 = set(query2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union) if union else 0.0

    def _get_document_suggestions(self) -> list[str]:
        """Generate suggestions based on available documents."""
        suggestions = []
        if settings.raw_dir.exists():
            companies = [d.name for d in settings.raw_dir.iterdir() if d.is_dir()]
            for company in companies[:3]:
                suggestions.append(f"What is {company}'s revenue in 2024?")
                suggestions.append(f"What are {company}'s main risk factors?")
                suggestions.append(f"Compare {company}'s financial performance")
        return suggestions

    def _get_default_suggestions(self) -> list[str]:
        """Get default suggestions."""
        return [
            "What was Microsoft's revenue in 2024?",
            "Compare Amazon and Google revenue growth",
            "What are Tesla's main risk factors?",
            "Analyze Apple's profit margins",
            "What is NVIDIA's market share?",
        ]

    def record_query(self, query: str) -> None:
        """Record a query for future suggestions."""
        # This is handled by CostTracker, but we can add additional logic here
        pass
