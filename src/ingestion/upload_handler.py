"""Handle document upload, parsing, and ingestion into vector store."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)

# Upload directory
UPLOAD_DIR = settings.data_dir / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# In-memory upload status tracking
_upload_status: dict[str, dict] = {}


def _generate_doc_id() -> str:
    return f"doc_{uuid.uuid4().hex[:12]}"


def validate_upload(filename: str, size: int) -> tuple[bool, str]:
    """Validate file before upload. Returns (valid, message)."""
    if not filename.lower().endswith(".pdf"):
        return False, "Only PDF files are supported"
    if size > 100 * 1024 * 1024:  # 100MB
        return False, "File size exceeds 100MB limit"
    if size == 0:
        return False, "File is empty"
    return True, "ok"


def save_upload(file_bytes: bytes, filename: str, ticker: str, year: str) -> str:
    """Save uploaded file and return doc_id."""
    doc_id = _generate_doc_id()
    doc_dir = UPLOAD_DIR / ticker / year
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    file_path = doc_dir / f"{doc_id}_{filename}"
    file_path.write_bytes(file_bytes)

    # Initialize status
    _upload_status[doc_id] = {
        "doc_id": doc_id,
        "filename": filename,
        "ticker": ticker.upper(),
        "year": year,
        "status": "processing",
        "chunk_count": 0,
        "file_path": str(file_path),
        "error": None,
    }

    return doc_id


def process_upload(doc_id: str) -> dict:
    """Parse, chunk, and embed uploaded document. Returns status dict."""
    status = _upload_status.get(doc_id)
    if not status:
        return {"status": "error", "error": "Document not found"}

    file_path = Path(status["file_path"])
    ticker = status["ticker"]
    year = status["year"]

    try:
        # Parse PDF using Docling
        text = _parse_pdf(file_path)
        if not text.strip():
            raise ValueError("No text extracted from PDF")

        # Chunk text
        chunks = _chunk_text(text, ticker, year)
        if not chunks:
            raise ValueError("No chunks generated from document")

        # Add to vector store
        from src.retrieval.vector_store import VectorStore
        vs = VectorStore()
        count = vs.add_documents(chunks, ticker)

        # Update status
        status["status"] = "indexed"
        status["chunk_count"] = count

        logger.info(f"Processed {doc_id}: {count} chunks from {ticker}/{year}")
        return status

    except Exception as e:
        status["status"] = "error"
        status["error"] = str(e)
        logger.error(f"Failed to process {doc_id}: {e}")
        return status


def get_upload_status(doc_id: str) -> dict | None:
    """Get upload status by doc_id."""
    return _upload_status.get(doc_id)


def list_uploads() -> list[dict]:
    """List all uploads."""
    return list(_upload_status.values())


def delete_upload(doc_id: str) -> bool:
    """Delete uploaded document from vector store and disk."""
    status = _upload_status.get(doc_id)
    if not status:
        return False

    # Remove from disk
    file_path = Path(status["file_path"])
    if file_path.exists():
        file_path.unlink()

    # Remove from status
    del _upload_status[doc_id]

    logger.info(f"Deleted upload {doc_id}")
    return True


def _parse_pdf(file_path: Path) -> str:
    """Parse PDF using Docling."""
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(file_path))
        return result.document.export_to_markdown()
    except ImportError:
        logger.warning("Docling not available, trying basic PDF extraction")
        return _parse_pdf_basic(file_path)
    except Exception as e:
        logger.warning(f"Docling failed: {e}, trying basic extraction")
        return _parse_pdf_basic(file_path)


def _parse_pdf_basic(file_path: Path) -> str:
    """Basic PDF text extraction fallback."""
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(file_path))
        text_parts = []
        for page in pdf:
            text_page = page.get_textpage()
            text_parts.append(text_page.get_text_range())
        return "\n\n".join(text_parts)
    except ImportError:
        # Last resort: read as binary and try to find text
        logger.warning("No PDF library available")
        return ""


def _chunk_text(text: str, ticker: str, year: str, max_chunk_size: int = 500) -> list[dict]:
    """Chunk text into smaller pieces with metadata."""
    import re

    chunks = []
    # Split into sections
    sections = []
    current_header = "preamble"
    current_content = ""

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            current_content += "\n"
            continue

        if re.match(r"^(ITEM|PART|Section)\s+\d", line, re.IGNORECASE):
            if current_content.strip():
                sections.append({"header": current_header, "content": current_content})
            current_header = line
            current_content = ""
        else:
            current_content += line + "\n"

    if current_content.strip():
        sections.append({"header": current_header, "content": current_content})

    # Create chunks from sections
    for section in sections:
        content = section["content"].strip()
        if not content:
            continue

        # Split by sentences
        sentences = re.split(r'(?<=[.!?])\s+', content)
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) > max_chunk_size and current_chunk:
                chunks.append({
                    "text": f"[{section['header']}] {current_chunk.strip()}",
                    "metadata": {
                        "ticker": ticker,
                        "year": year,
                        "section": section["header"],
                        "chunk_index": len(chunks),
                    },
                })
                current_chunk = sentence
            else:
                current_chunk += " " if current_chunk else ""
                current_chunk += sentence

        if current_chunk.strip() and len(current_chunk.strip()) > 50:
            chunks.append({
                "text": f"[{section['header']}] {current_chunk.strip()}",
                "metadata": {
                    "ticker": ticker,
                    "year": year,
                    "section": section["header"],
                    "chunk_index": len(chunks),
                },
            })

    return chunks
