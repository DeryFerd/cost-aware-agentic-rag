"""Parse SEC 10-K documents using Docling."""

from __future__ import annotations

import logging
from pathlib import Path

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.chunking import HybridChunker

from src.config import settings

logger = logging.getLogger(__name__)


def _get_converter() -> DocumentConverter:
    """Create a Docling converter with optimized settings for financial docs."""
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = True

    return DocumentConverter(
        format_options={
            "pdf": PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


def parse_document(file_path: Path) -> dict:
    """Parse a single document and return structured content.

    Returns:
        dict with keys: title, sections, tables, figures, metadata
    """
    converter = _get_converter()
    result = converter.convert(str(file_path))
    doc = result.document

    sections = []
    tables = []
    figures = []

    for item in doc.texts:
        if item.label == "section_header":
            sections.append(
                {
                    "title": item.text,
                    "level": getattr(item, "level", 1),
                }
            )
        elif item.label == "table":
            tables.append(
                {
                    "content": item.text,
                    "export": getattr(item, "export_to_dataframe", None),
                }
            )
        elif item.label == "figure":
            figures.append(
                {
                    "caption": item.text,
                    "image": getattr(item, "image", None),
                }
            )

    return {
        "title": doc.name if hasattr(doc, "name") else file_path.stem,
        "sections": sections,
        "tables": tables,
        "figures": figures,
        "text": doc.export_to_markdown(),
        "metadata": {
            "source": str(file_path),
            "pages": len(doc.pages) if hasattr(doc, "pages") else 0,
        },
    }


def chunk_document(file_path: Path) -> list[dict]:
    """Parse and chunk a document.

    For .txt files, uses simple paragraph chunking.
    For PDF/HTML, uses Docling HybridChunker.
    Returns list of chunks with metadata.
    """
    # Simple text file handling
    if file_path.suffix.lower() == ".txt":
        text = file_path.read_text(encoding="utf-8")
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks = []
        for i, para in enumerate(paragraphs):
            if len(para) > 50:  # Skip very short paragraphs
                chunks.append(
                    {
                        "text": para,
                        "metadata": {
                            "source": str(file_path),
                            "chunk_index": i,
                            "start_page": 0,
                            "end_page": 0,
                        },
                    }
                )
        return chunks

    # PDF/HTML handling with Docling
    converter = _get_converter()
    result = converter.convert(str(file_path))
    doc = result.document

    chunker = HybridChunker()
    chunks = list(chunker.chunk(doc))

    return [
        {
            "text": chunk.text,
            "metadata": {
                "source": str(file_path),
                "chunk_index": i,
                "start_page": getattr(chunk, "start_page", 0),
                "end_page": getattr(chunk, "end_page", 0),
            },
        }
        for i, chunk in enumerate(chunks)
    ]


def parse_all_documents() -> dict[str, list[dict]]:
    """Parse all downloaded documents and return chunked results."""
    results: dict[str, list[dict]] = {}

    for company_dir in settings.raw_dir.iterdir():
        if not company_dir.is_dir():
            continue

        ticker = company_dir.name
        all_chunks: list[dict] = []

        for file_path in company_dir.rglob("*"):
            if file_path.suffix.lower() in (".pdf", ".html", ".htm"):
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
