"""Contextual embeddings — prepend chunk-level context before embedding.

Based on Anthropic's September 2024 research:
- 49% reduction in retrieval failures with contextual embeddings
- 67% with contextual embeddings + BM25 + reranker
- Cost: ~$1/1M document tokens with prompt caching

This module generates a 50-100 token context for each chunk that situates
it within the parent document, then prepends it before embedding.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.config import settings
from src.generation.llm_client import OllamaClient

logger = logging.getLogger(__name__)

CONTEXTUALIZATION_PROMPT = """Here is a full document. Below is a chunk extracted from it.

Write a 50-100 token context that explains where this chunk sits in the document
and what broader topic it relates to. Be specific about the document section,
company, and time period if mentioned.

Do NOT repeat the chunk content. Only add contextual framing.

Document:
{document}

Chunk:
{chunk}

Context (50-100 tokens):"""


@dataclass
class ContextualChunk:
    """A chunk with prepended contextual information."""
    original_text: str
    contextual_text: str  # original_text with context prepended
    context_summary: str  # just the context part


class ContextualEmbedder:
    """Prepend document-level context to each chunk before embedding.

    This is the single highest-ROI improvement for RAG in 2026.
    Each chunk gets a 50-100 token context that situates it within
    the parent document, dramatically improving retrieval accuracy.
    """

    def __init__(self, max_context_tokens: int = 100):
        self.max_context_tokens = max_context_tokens
        self._llm = None

    def _get_llm(self) -> OllamaClient:
        if self._llm is None:
            self._llm = OllamaClient()
        return self._llm

    def generate_context(
        self,
        document_text: str,
        chunk_text: str,
    ) -> str:
        """Generate a 50-100 token context for a chunk within its document.

        Args:
            document_text: Full parent document text (truncated to fit context window)
            chunk_text: The chunk to contextualize

        Returns:
            A 50-100 token context string
        """
        llm = self._get_llm()

        # Truncate document to fit in context window (keep first 3000 chars)
        doc_truncated = document_text[:3000]
        if len(document_text) > 3000:
            doc_truncated += "\n[...truncated...]"

        prompt = CONTEXTUALIZATION_PROMPT.format(
            document=doc_truncated,
            chunk=chunk_text[:1000],
        )

        try:
            resp = llm.chat(
                model=settings.ollama_simple_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=150,
            )
            context = resp.content.strip()

            # Enforce token limit (rough: 1 token ≈ 4 chars)
            max_chars = self.max_context_tokens * 4
            if len(context) > max_chars:
                context = context[:max_chars].rsplit(" ", 1)[0]

            return context

        except Exception as e:
            logger.warning(f"Context generation failed: {e}")
            # Fallback: use section metadata if available
            return ""

    def contextualize_chunk(
        self,
        document_text: str,
        chunk_text: str,
        metadata: dict | None = None,
    ) -> ContextualChunk:
        """Prepend context to a single chunk.

        Args:
            document_text: Full parent document
            chunk_text: The chunk to contextualize
            metadata: Optional metadata (section, ticker, year)

        Returns:
            ContextualChunk with original and contextual text
        """
        metadata = metadata or {}

        # Build context from metadata + LLM
        meta_context = ""
        if metadata.get("ticker"):
            meta_context = f"From {metadata['ticker']} "
        if metadata.get("year"):
            meta_context += f"({metadata['year']}) "
        if metadata.get("section"):
            meta_context += f"in section '{metadata['section']}': "

        # Generate LLM context
        llm_context = self.generate_context(document_text, chunk_text)

        # Combine metadata context + LLM context
        full_context = f"{meta_context}{llm_context}".strip()

        contextual_text = f"[Context: {full_context}]\n\n{chunk_text}" if full_context else chunk_text

        return ContextualChunk(
            original_text=chunk_text,
            contextual_text=contextual_text,
            context_summary=full_context,
        )

    def contextualize_chunks(
        self,
        document_text: str,
        chunks: list[dict],
    ) -> list[dict]:
        """Contextualize a batch of chunks.

        Args:
            document_text: Full parent document
            chunks: List of dicts with 'text' and 'metadata' keys

        Returns:
            List of chunks with 'contextual_text' added to metadata
        """
        contextualized = []

        for chunk in chunks:
            result = self.contextualize_chunk(
                document_text=document_text,
                chunk_text=chunk["text"],
                metadata=chunk.get("metadata", {}),
            )

            # Add contextual text to chunk metadata
            new_metadata = {**chunk.get("metadata", {})}
            new_metadata["contextual_text"] = result.contextual_text
            new_metadata["context_summary"] = result.context_summary

            contextualized.append({
                **chunk,
                "metadata": new_metadata,
            })

        logger.info(f"Contextualized {len(chunks)} chunks")
        return contextualized
