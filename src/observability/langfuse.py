"""Langfuse observability integration."""

from __future__ import annotations

import logging
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

# Try to import langfuse, optional dependency
try:
    from langfuse import Langfuse
    from langfuse.callback import CallbackHandler
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    logger.info("Langfuse not installed. Install with: pip install langfuse")


class Observability:
    """Wrapper for Langfuse observability."""

    def __init__(self) -> None:
        self.enabled = False
        self.client = None
        self.handler = None

        if LANGFUSE_AVAILABLE and settings.langfuse_public_key:
            try:
                self.client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
                self.handler = CallbackHandler(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
                self.enabled = True
                logger.info("Langfuse observability enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")
        else:
            logger.info("Langfuse disabled (not configured or not installed)")

    def track_query(
        self,
        query: str,
        answer: str,
        model: str,
        complexity: str,
        cost_usd: float,
        latency_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Track a query execution."""
        if not self.enabled or not self.client:
            return

        try:
            self.client.trace(
                name="rag_query",
                input=query,
                output=answer,
                metadata={
                    "model": model,
                    "complexity": complexity,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                    **(metadata or {}),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to track query: {e}")

    def get_handler(self):
        """Get callback handler for LangChain/LlamaIndex."""
        return self.handler


# Global instance
observability = Observability()
