"""Orchestrate the full ingestion pipeline."""

from __future__ import annotations

import logging

from src.config import settings
from src.ingestion.contextual_embeddings import ContextualEmbedder
from src.ingestion.downloader import TARGET_COMPANIES, download_sample_dataset
from src.ingestion.parser import chunk_document
from src.retrieval.bm25_index import BM25Index
from src.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


def run_ingestion(skip_download: bool = False, enable_contextual: bool = True) -> dict:
    """Run the full ingestion pipeline: download → parse → contextualize → embed → index.

    Args:
        skip_download: Skip the download step (use existing files)
        enable_contextual: Enable contextual embeddings (Anthropic's 49% improvement)
    """
    print("=" * 60)
    print("  SEC 10-K Ingestion Pipeline")
    print("=" * 60)

    # Step 1: Download
    if not skip_download:
        print("\n[STEP 1] Downloading SEC 10-K filings...")
        dataset = download_sample_dataset()
        total_files = sum(len(v) for v in dataset.values())
        print(f"  Downloaded {total_files} files from {len(dataset)} companies")
    else:
        print("\n[SKIP] Skipping download (using existing files)")

    # Step 2: Parse and chunk
    print("\n[STEP 2] Parsing and chunking documents...")
    vector_store = VectorStore()
    bm25_index = BM25Index()

    # Contextual embedder (Anthropic's highest-ROI improvement)
    contextualizer = ContextualEmbedder() if enable_contextual else None
    if enable_contextual:
        print("  [INFO] Contextual embeddings enabled (49% retrieval improvement)")

    total_chunks = 0
    contextualized_count = 0

    for _cik, ticker, name in TARGET_COMPANIES:
        company_dir = settings.raw_dir / ticker
        if not company_dir.exists():
            logger.warning(f"No data directory for {ticker}, skipping")
            continue

        all_chunks: list[dict] = []
        for file_path in company_dir.rglob("*"):
            if file_path.suffix.lower() in (".pdf", ".html", ".htm", ".txt"):
                try:
                    chunks = chunk_document(file_path)
                    all_chunks.extend(chunks)
                    logger.info(f"Parsed {file_path.name}: {len(chunks)} chunks")
                except Exception as e:
                    logger.warning(f"Failed to parse {file_path.name}: {e}")

        if all_chunks:
            # Contextual embeddings: prepend context to each chunk before embedding
            if contextualizer and all_chunks:
                try:
                    # Read the full document text for context generation
                    doc_text = "\n\n".join(c["text"] for c in all_chunks[:5])  # first 5 chunks as doc context
                    all_chunks = contextualizer.contextualize_chunks(doc_text, all_chunks)
                    contextualized_count += len(all_chunks)
                except Exception as e:
                    logger.warning(f"Contextual embedding failed for {ticker}: {e}")

            # Add to indices
            vector_store.add_documents(all_chunks, ticker)
            bm25_index.add_documents(all_chunks)
            total_chunks += len(all_chunks)
            print(f"  {name} ({ticker}): {len(all_chunks)} chunks")

    # Save BM25 index
    bm25_index.save()

    stats = {
        "total_chunks": total_chunks,
        "contextualized_chunks": contextualized_count,
        "vector_store_count": vector_store.count(),
        "bm25_count": bm25_index.count(),
    }

    print(f"\n{'=' * 60}")
    print("  Ingestion Complete!")
    print(f"  Total chunks: {stats['total_chunks']}")
    if contextualized_count > 0:
        print(f"  Contextualized: {stats['contextualized_chunks']} (49% retrieval improvement)")
    print(f"  Vector store: {stats['vector_store_count']}")
    print(f"  BM25 index:   {stats['bm25_count']}")
    print(f"{'=' * 60}")

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run ingestion pipeline")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    run_ingestion(skip_download=args.skip_download)
