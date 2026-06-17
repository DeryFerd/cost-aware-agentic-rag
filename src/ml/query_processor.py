"""Query processing: rewriting, HyDE, and multi-query expansion."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProcessedQuery:
    """Result of query processing."""
    original: str
    rewritten: str
    hyde_query: str | None = None
    expanded_queries: list[str] | None = None


class QueryProcessor:
    """Process queries for better retrieval."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def process(
        self,
        query: str,
        enable_rewrite: bool = True,
        enable_hyde: bool = True,
        enable_multi_query: bool = True,
    ) -> ProcessedQuery:
        """Process a query with all available techniques.

        Args:
            query: The original user query
            enable_rewrite: Enable query rewriting
            enable_hyde: Enable HyDE (Hypothetical Document Embeddings)
            enable_multi_query: Enable multi-query expansion

        Returns:
            ProcessedQuery with all variations
        """
        result = ProcessedQuery(original=query, rewritten=query)

        # Step 1: Query rewriting
        if enable_rewrite:
            result.rewritten = self._rewrite_query(query)

        # Step 2: HyDE
        if enable_hyde and self.llm:
            result.hyde_query = self._generate_hyde(result.rewritten)

        # Step 3: Multi-query expansion
        if enable_multi_query and self.llm:
            result.expanded_queries = self._expand_multi_query(result.rewritten)

        return result

    def _rewrite_query(self, query: str) -> str:
        """Rewrite query for better retrieval.

        - Resolve pronouns
        - Expand abbreviations
        - Add context
        """
        # Simple rule-based rewriting
        rewritten = query

        # Expand common abbreviations in financial context
        abbreviations = {
            r"\btheir\b": "the company's",
            r"\bit\b": "the company",
            r"\bthis year\b": "2024",
            r"\blast year\b": "2023",
            r"\brevenue\b": "total revenue",
            r"\bprofit\b": "net income",
        }

        for pattern, replacement in abbreviations.items():
            rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)

        # If query is very short, add context
        tickers = ["MSFT", "AMZN", "TSLA", "GOOG", "META", "AAPL", "NVDA"]
        has_ticker = any(t in query.upper() for t in tickers)
        if len(query.split()) < 4 and not has_ticker:
            rewritten = f"SEC 10-K filing {rewritten}"

        return rewritten

    def _generate_hyde(self, query: str) -> str | None:
        """Generate a Hypothetical Document Embedding (HyDE).

        Generate a hypothetical answer, then use it for retrieval.
        """
        if not self.llm:
            return None

        try:
            prompt = f"""Write a short, factual paragraph that would answer this question.
Focus on specific numbers, dates, and facts. Do NOT make up information.

Question: {query}

Hypothetical answer:"""

            response = self.llm.chat(
                model="gemma3:4b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )

            return response.get("content", "").strip()
        except Exception as e:
            logger.warning(f"HyDE generation failed: {e}")
            return None

    def _expand_multi_query(self, query: str) -> list[str] | None:
        """Generate multiple query variations for better recall."""
        if not self.llm:
            return None

        try:
            prompt = (
                "Generate 3 different search queries that would find "
                "the same information as this query. Each query should "
                "approach the topic from a different angle.\n\n"
                f"Original query: {query}\n\n"
                "Return ONLY the 3 queries, one per line:"
            )

            response = self.llm.chat(
                model="gemma3:4b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200,
            )

            content = response.get("content", "")
            queries = [q.strip() for q in content.strip().split("\n") if q.strip()]

            # Filter out queries too similar to original
            expanded = []
            for q in queries[:3]:
                if q.lower() != query.lower() and len(q.split()) >= 3:
                    expanded.append(q)

            return expanded if expanded else None
        except Exception as e:
            logger.warning(f"Multi-query expansion failed: {e}")
            return None

    def get_all_queries(self, processed: ProcessedQuery) -> list[str]:
        """Get all query variations for retrieval.

        Returns:
            List of unique queries to retrieve with
        """
        queries = [processed.rewritten]

        if processed.hyde_query:
            queries.append(processed.hyde_query)

        if processed.expanded_queries:
            queries.extend(processed.expanded_queries)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for q in queries:
            q_lower = q.lower().strip()
            if q_lower not in seen:
                seen.add(q_lower)
                unique.append(q)

        return unique
