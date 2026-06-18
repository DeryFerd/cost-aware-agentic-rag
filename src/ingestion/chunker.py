"""Semantic chunker with parent-child hierarchy and overlap."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A chunk of text with metadata."""
    text: str
    chunk_id: str = ""
    parent_id: str = ""
    section: str = ""
    start_idx: int = 0
    end_idx: int = 0
    token_estimate: int = 0
    metadata: dict = field(default_factory=dict)


class SemanticChunker:
    """Chunk text using semantic boundaries with parent-child hierarchy.

    Features:
    - Recursive splitting (paragraph → sentence → word)
    - Overlap between chunks for context continuity
    - Parent-child hierarchy (small for retrieval, large for context)
    - Section-aware splitting
    """

    def __init__(
        self,
        child_max_tokens: int = 256,
        parent_max_tokens: int = 1024,
        overlap_tokens: int = 50,
        min_chunk_tokens: int = 50,
    ):
        self.child_max_tokens = child_max_tokens
        self.parent_max_tokens = parent_max_tokens
        self.overlap_tokens = overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens

    def chunk_text(
        self,
        text: str,
        section: str = "",
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """Chunk text with parent-child hierarchy.

        Args:
            text: Full document text
            section: Section heading
            metadata: Additional metadata for all chunks

        Returns:
            List of Chunk objects (parent chunks with child references)
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        chunks = []

        # Split into sections first
        sections = self._split_into_sections(text)

        for section_name, section_text in sections:
            # Create parent chunks (large)
            parent_chunks = self._create_parent_chunks(section_text, section_name)

            for parent_idx, parent_text in enumerate(parent_chunks):
                parent_id = f"{section_name}_{parent_idx}" if section_name else f"parent_{parent_idx}"

                # Create child chunks (small) from parent
                child_chunks = self._create_child_chunks(parent_text, parent_id)

                # Add parent chunk
                token_est = self._estimate_tokens(parent_text)
                chunks.append(Chunk(
                    text=parent_text,
                    chunk_id=parent_id,
                    section=section_name,
                    token_estimate=token_est,
                    metadata={**metadata, "type": "parent"},
                ))

                # Add child chunks
                for child_idx, child_text in enumerate(child_chunks):
                    child_id = f"{parent_id}_child_{child_idx}"
                    child_token_est = self._estimate_tokens(child_text)
                    chunks.append(Chunk(
                        text=child_text,
                        chunk_id=child_id,
                        parent_id=parent_id,
                        section=section_name,
                        token_estimate=child_token_est,
                        metadata={**metadata, "type": "child"},
                    ))

        return chunks

    def _split_into_sections(self, text: str) -> list[tuple[str, str]]:
        """Split text into sections based on headings."""
        # Match common heading patterns
        heading_pattern = r'^(?:ITEM|PART|Section)\s+\d+[.:]\s*.*$'
        sections = []
        current_heading = "preamble"
        current_content = []

        for line in text.split("\n"):
            if re.match(heading_pattern, line.strip(), re.IGNORECASE):
                if current_content:
                    sections.append((current_heading, "\n".join(current_content)))
                current_heading = line.strip()
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections.append((current_heading, "\n".join(current_content)))

        return sections if sections else [("document", text)]

    def _create_parent_chunks(self, text: str, section: str) -> list[str]:
        """Create parent chunks (larger, for context)."""
        paragraphs = self._split_into_paragraphs(text)
        parents = []
        current_parent = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)

            if current_tokens + para_tokens > self.parent_max_tokens and current_parent:
                parents.append("\n\n".join(current_parent))
                current_parent = [para]
                current_tokens = para_tokens
            else:
                current_parent.append(para)
                current_tokens += para_tokens

        if current_parent:
            parents.append("\n\n".join(current_parent))

        return parents if parents else [text[:2000]]

    def _create_child_chunks(self, text: str, parent_id: str) -> list[str]:
        """Create child chunks (smaller, for retrieval)."""
        sentences = self._split_into_sentences(text)
        children = []
        current_child = []
        current_tokens = 0

        for sent in sentences:
            sent_tokens = self._estimate_tokens(sent)

            if current_tokens + sent_tokens > self.child_max_tokens and current_child:
                child_text = " ".join(current_child)
                children.append(child_text)

                # Add overlap from end of previous chunk
                overlap_sents = current_child[-2:] if len(current_child) > 2 else current_child
                current_child = overlap_sents + [sent]
                current_tokens = self._estimate_tokens(" ".join(current_child))
            else:
                current_child.append(sent)
                current_tokens += sent_tokens

        if current_child:
            children.append(" ".join(current_child))

        # Filter very short chunks
        children = [c for c in children if self._estimate_tokens(c) >= self.min_chunk_tokens]

        return children if children else [text[:500]]

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """Split text into paragraphs."""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: 1 token ≈ 4 chars)."""
        return len(text) // 4


class ParentChildChunker:
    """Simple parent-child chunker without semantic analysis.

    Faster alternative to SemanticChunker for large documents.
    """

    def __init__(
        self,
        child_max_chars: int = 500,
        parent_max_chars: int = 2000,
        overlap_chars: int = 100,
    ):
        self.child_max_chars = child_max_chars
        self.parent_max_chars = parent_max_chars
        self.overlap_chars = overlap_chars

    def chunk(
        self,
        text: str,
        metadata: dict | None = None,
    ) -> list[dict]:
        """Chunk text into parent-child hierarchy.

        Returns:
            List of dicts with 'text', 'type', 'parent_id', 'metadata'
        """
        if not text:
            return []

        metadata = metadata or {}
        chunks = []

        # Split into paragraphs
        paragraphs = text.split("\n\n")

        # Create parents from paragraphs
        current_parent = []
        current_len = 0
        parent_idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if current_len + len(para) > self.parent_max_chars and current_parent:
                parent_text = "\n\n".join(current_parent)
                parent_id = f"parent_{parent_idx}"

                # Add parent
                chunks.append({
                    "text": parent_text,
                    "type": "parent",
                    "chunk_id": parent_id,
                    "metadata": {**metadata, "section": parent_id},
                })

                # Create children from parent
                children = self._split_to_children(parent_text)
                for child_idx, child_text in enumerate(children):
                    chunks.append({
                        "text": child_text,
                        "type": "child",
                        "chunk_id": f"{parent_id}_child_{child_idx}",
                        "parent_id": parent_id,
                        "metadata": {**metadata, "section": parent_id},
                    })

                parent_idx += 1
                current_parent = [para]
                current_len = len(para)
            else:
                current_parent.append(para)
                current_len += len(para)

        # Handle last parent
        if current_parent:
            parent_text = "\n\n".join(current_parent)
            parent_id = f"parent_{parent_idx}"
            chunks.append({
                "text": parent_text,
                "type": "parent",
                "chunk_id": parent_id,
                "metadata": {**metadata, "section": parent_id},
            })
            children = self._split_to_children(parent_text)
            for child_idx, child_text in enumerate(children):
                chunks.append({
                    "text": child_text,
                    "type": "child",
                    "chunk_id": f"{parent_id}_child_{child_idx}",
                    "parent_id": parent_id,
                    "metadata": {**metadata, "section": parent_id},
                })

        return chunks

    def _split_to_children(self, text: str) -> list[str]:
        """Split parent text into child-sized chunks with overlap."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        children = []
        current = []
        current_len = 0

        for sent in sentences:
            if current_len + len(sent) > self.child_max_chars and current:
                children.append(" ".join(current))
                # Add overlap
                overlap_sents = current[-1:] if current else []
                current = overlap_sents + [sent]
                current_len = len(" ".join(current))
            else:
                current.append(sent)
                current_len += len(sent)

        if current:
            children.append(" ".join(current))

        return children
