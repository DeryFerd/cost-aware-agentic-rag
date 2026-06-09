"""Parse SEC 10-K documents using Docling."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)


def _extract_metadata(file_path: Path) -> dict:
    """Extract ticker, year, and section from file path."""
    parts = file_path.parts
    ticker = None
    year = None

    # Find ticker and year from path
    for part in parts:
        if part.upper() in ["MSFT", "AMZN", "META", "GOOG", "TSLA", "AAPL", "NVDA"]:
            ticker = part.upper()
        if re.match(r"^20\d{2}$", part):
            year = part

    return {
        "ticker": ticker or "UNKNOWN",
        "year": year or "UNKNOWN",
    }


def _split_into_sections(text: str) -> list[dict]:
    """Split text into sections based on headers."""
    sections = []
    current_section = {"header": " preamble", "content": ""}

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            current_section["content"] += "\n"
            continue

        # Detect section headers (ITEM X, PART X, etc.)
        if re.match(r"^(ITEM|PART|Section)\s+\d", line, re.IGNORECASE):
            if current_section["content"].strip():
                sections.append(current_section)
            current_section = {"header": line, "content": ""}
        else:
            current_section["content"] += line + "\n"

    if current_section["content"].strip():
        sections.append(current_section)

    return sections


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def _create_chunks_from_section(
    section: dict,
    metadata: dict,
    max_chunk_size: int = 500,
) -> list[dict]:
    """Create smaller chunks from a section."""
    content = section["content"].strip()
    if not content:
        return []

    chunks = []
    sentences = _split_into_sentences(content)

    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) > max_chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += " " + sentence if current_chunk else sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    result = []
    for i, chunk in enumerate(chunks):
        if len(chunk) > 50:  # Skip very short chunks
            result.append({
                "text": f"[{section['header']}] {chunk}",
                "metadata": {
                    **metadata,
                    "section": section["header"],
                    "chunk_index": i,
                },
            })

    return result


def chunk_document(file_path: Path) -> list[dict]:
    """Parse and chunk a document into smaller, targeted chunks.

    For .txt files: splits by section headers, then by sentences.
    Returns list of chunks with company/year metadata.
    """
    metadata = _extract_metadata(file_path)

    if file_path.suffix.lower() == ".txt":
        text = file_path.read_text(encoding="utf-8")
    elif file_path.suffix.lower() in (".pdf", ".html", ".htm"):
        # For now, treat as text (PDF parsing needs Docling)
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    else:
        return []

    # Split into sections
    sections = _split_into_sections(text)

    # Create chunks from each section
    all_chunks = []
    for section in sections:
        chunks = _create_chunks_from_section(section, metadata)
        all_chunks.extend(chunks)

    return all_chunks


def parse_all_documents() -> dict[str, list[dict]]:
    """Parse all downloaded documents and return chunked results."""
    results: dict[str, list[dict]] = {}

    for company_dir in settings.raw_dir.iterdir():
        if not company_dir.is_dir():
            continue

        ticker = company_dir.name
        all_chunks: list[dict] = []

        for file_path in company_dir.rglob("*"):
            if file_path.suffix.lower() in (".pdf", ".html", ".htm", ".txt"):
                try:
                    chunks = chunk_document(file_path)
                    all_chunks.extend(chunks)
                    logger.info(f"Parsed {file_path.name}: {len(chunks)} chunks")
                except Exception as e:
                    logger.warning(f"Failed to parse {file_path.name}: {e}")

        results[ticker] = all_chunks

    return results


if __name__ == "__main__":
    results = parse_all_documents()
    for ticker, chunks in results.items():
        print(f"  {ticker}: {len(chunks)} chunks")
