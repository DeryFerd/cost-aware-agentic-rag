"""Celery tasks for background processing.

NOTE: These tasks are defined for future SaaS functionality but are NOT currently
triggered by the API. The system currently processes queries synchronously.
To enable Celery tasks, you need to:
1. Start a Redis server
2. Start a Celery worker: celery -A src.tasks.celery_app worker --loglevel=info
3. Call tasks asynchronously: ingest_document.delay(file_path, ticker, year)
"""

from celery import Celery
from celery.utils.log import get_task_logger

from src.config import settings

logger = get_task_logger(__name__)

# Celery app
app = Celery(
    "cost_aware_rag",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
)


@app.task(bind=True, name="tasks.ingest_document")
def ingest_document(self, file_path: str, ticker: str, year: int):
    """Ingest a document into the vector store."""
    from pathlib import Path
    from src.ingestion.parser import chunk_document
    from src.retrieval.vector_store import VectorStore
    from src.retrieval.bm25_index import BM25Index

    logger.info(f"Ingesting {ticker} {year} from {file_path}")

    try:
        # Update task state
        self.update_state(state="PROGRESS", meta={"status": "parsing"})

        # Parse document
        chunks = chunk_document(Path(file_path))
        logger.info(f"Parsed {len(chunks)} chunks")

        # Add to vector store
        self.update_state(state="PROGRESS", meta={"status": "embedding"})
        store = VectorStore()
        store.add_documents(chunks, ticker)

        # Add to BM25 index
        self.update_state(state="PROGRESS", meta={"status": "indexing"})
        bm25 = BM25Index()
        bm25.load()
        bm25.add_documents(chunks)
        bm25.save()

        logger.info(f"Successfully ingested {ticker} {year}")
        return {"status": "success", "chunks": len(chunks)}

    except Exception as e:
        logger.error(f"Failed to ingest {ticker} {year}: {e}")
        raise self.retry(exc=e, countdown=60)


@app.task(bind=True, name="tasks.batch_query")
def batch_query(self, queries: list[dict], model: str = "gemma3:4b"):
    """Process multiple queries in batch."""
    from src.agents.graph import LangGraphOrchestrator

    logger.info(f"Processing batch of {len(queries)} queries")

    orchestrator = LangGraphOrchestrator()
    results = []

    for i, query_data in enumerate(queries):
        try:
            self.update_state(
                state="PROGRESS",
                meta={"current": i + 1, "total": len(queries)},
            )

            result = orchestrator.run(query_data["question"])
            results.append({
                "question": query_data["question"],
                "answer": result["answer"],
                "model": result["model_used"],
                "cost": result["total_cost_usd"],
            })
        except Exception as e:
            logger.error(f"Query {i} failed: {e}")
            results.append({
                "question": query_data["question"],
                "error": str(e),
            })

    return {"status": "success", "results": results}


@app.task(name="tasks.rebuild_index")
def rebuild_index():
    """Rebuild the entire search index."""
    from src.ingestion.parser import parse_all_documents
    from src.retrieval.vector_store import VectorStore
    from src.retrieval.bm25_index import BM25Index
    from src.config import settings

    logger.info("Rebuilding search index")

    # Parse all documents
    results = parse_all_documents()

    # Rebuild vector store
    store = VectorStore()
    store.delete_all()
    for ticker, chunks in results.items():
        store.add_documents(chunks, ticker)

    # Rebuild BM25 index
    bm25 = BM25Index()
    for ticker, chunks in results.items():
        bm25.add_documents(chunks)
    bm25.save(settings.indexes_dir / "bm25.pkl")

    total_chunks = sum(len(chunks) for chunks in results.values())
    logger.info(f"Index rebuilt with {total_chunks} chunks")
    return {"status": "success", "total_chunks": total_chunks}


@app.task(name="tasks.cleanup_old_cache")
def cleanup_old_cache():
    """Clean up old cache entries."""
    from src.database.cache import cache

    # This would implement cache cleanup logic
    logger.info("Cleaning up old cache entries")
    return {"status": "success"}
