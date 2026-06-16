"""FastAPI application for Cost-Aware Agentic RAG."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import UploadFile, File, Form, BackgroundTasks

from api.models import (
    QueryRequest,
    QueryResponse,
    CostSummary,
    HealthResponse,
    UploadResponse,
    UploadStatus,
    FeedbackRequest,
    FeedbackStats,
)
from src.agents.graph import LangGraphOrchestrator
from src.generation.cost_tracker import CostTracker, QueryCostRecord
from src.agents.memory import memory
from src.agents.guardrails import guardrails
from src.config import settings
from src.database.cache import cache
from src.ingestion.upload_handler import (
    validate_upload,
    save_upload,
    process_upload,
    get_upload_status,
    list_uploads,
    delete_upload,
)
from src.ml.feedback import store_feedback, get_feedback_stats, get_recent_feedback
from src.ml.cost_analytics import CostAnalytics
from src.ml.export import QueryExporter

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Cost-Aware Agentic RAG",
    description="Production-grade RAG for SEC 10-K Financial Analysis",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
web_dir = project_root / "web"
app.mount("/static", StaticFiles(directory=str(web_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(web_dir / "templates"))

# Initialize components
orchestrator = LangGraphOrchestrator()
cost_tracker = CostTracker()


@app.on_event("startup")
async def startup_event():
    """Load indices on startup."""
    try:
        from src.retrieval.hybrid import HybridRetriever
        retriever = HybridRetriever()
        retriever.load_indices()
        logger.info("Indices loaded successfully")
    except Exception as e:
        logger.warning(f"Could not load indices: {e}")


# ── Web Pages ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def landing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@app.get("/app", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "app.html")


@app.get("/app/documents", response_class=HTMLResponse)
def documents_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "documents.html")


@app.get("/app/analytics", response_class=HTMLResponse)
def analytics_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "analytics.html")


# ── API Endpoints ──────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        # Count actual documents (10-K filings)
        doc_count = 0
        if settings.raw_dir.exists():
            for company_dir in settings.raw_dir.iterdir():
                if company_dir.is_dir():
                    for year_dir in company_dir.iterdir():
                        if year_dir.is_dir():
                            for f in year_dir.glob("*.txt"):
                                doc_count += 1

        from src.retrieval.vector_store import VectorStore
        vs = VectorStore()
        chunk_count = vs.count()

        return HealthResponse(
            status="ok",
            document_count=doc_count,
            chunk_count=chunk_count,
            version="0.1.0",
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}") from e


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    query_text = req.query.strip()

    # Input guardrails
    input_result = guardrails.validate_input(query_text)
    if not input_result.passed:
        raise HTTPException(status_code=400, detail=input_result.message)

    # Use sanitized input
    query_text = input_result.sanitized_input or query_text

    # Check Redis cache first
    try:
        cached = cache.get_query_cache(query_text, settings.ollama_simple_model)
        if cached:
            logger.info(f"Cache hit for query: {query_text[:50]}...")
            return QueryResponse(**cached)
    except Exception as e:
        logger.warning(f"Cache check failed: {e}")

    try:
        response = orchestrator.run(query_text)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {e}") from e

    # Output guardrails
    answer = response["answer"]
    output_result = guardrails.validate_output(
        answer=answer,
        context=response.get("context", ""),
        query=query_text,
    )
    if "add_disclaimer" in output_result.issues:
        answer = guardrails.output.add_disclaimer(answer)

    # Track cost
    try:
        cost_tracker.record(
            QueryCostRecord(
                query=query_text,
                model=response["model_used"],
                complexity=response["complexity"],
                tokens_in=0,
                tokens_out=0,
                cost_usd=response["total_cost_usd"],
                latency_ms=response["total_latency_ms"],
            )
        )
    except Exception as e:
        logger.warning(f"Cost tracking failed: {e}")

    result = QueryResponse(
        answer=answer,
        complexity=response["complexity"],
        model_used=response["model_used"],
        cost_usd=response["total_cost_usd"],
        latency_ms=response["total_latency_ms"],
        citations=response["citations"],
        steps_count=len(response["steps"]),
    )

    # Cache the result
    try:
        cache.set_query_cache(query_text, response["model_used"], result.model_dump())
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

    return result


@app.get("/cost/summary", response_model=CostSummary)
def cost_summary() -> CostSummary:
    try:
        summary = cost_tracker.summary()
        return CostSummary(**summary)
    except Exception as e:
        logger.error(f"Cost summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cost summary failed: {e}") from e


@app.get("/cost/budget")
def cost_budget():
    try:
        return cost_tracker.budget_check()
    except Exception as e:
        logger.error(f"Budget check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Budget check failed: {e}") from e


@app.get("/conversation/history")
def conversation_history():
    """Get conversation history."""
    return {"history": memory.get_history(limit=20)}


@app.get("/documents")
def list_documents():
    """List all indexed documents with metadata."""
    documents = []
    doc_id = 1

    if settings.raw_dir.exists():
        for company_dir in settings.raw_dir.iterdir():
            if company_dir.is_dir():
                ticker = company_dir.name
                for year_dir in company_dir.iterdir():
                    if year_dir.is_dir():
                        try:
                            year = int(year_dir.name)
                        except ValueError:
                            continue

                        # Count files and estimate chunks
                        files = list(year_dir.glob("*"))
                        txt_files = [f for f in files if f.suffix.lower() == ".txt"]
                        total_size = sum(f.stat().st_size for f in txt_files)

                        documents.append({
                            "id": doc_id,
                            "ticker": ticker,
                            "year": year,
                            "filing_type": "10-K",
                            "status": "indexed",
                            "chunks": max(10, total_size // 5000),  # rough estimate
                            "size": f"{total_size // 1024} KB" if total_size > 1024 else f"{total_size} B",
                        })
                        doc_id += 1

    return {"documents": documents}


@app.delete("/conversation/clear")
def clear_conversation():
    """Clear conversation history."""
    memory.clear()
    return {"status": "cleared"}


@app.post("/query/stream")
def query_stream(req: QueryRequest):
    """Stream response token by token for better UX."""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    import json

    SYSTEM_PROMPT = """You are a financial analyst AI specializing in SEC 10-K filings.

Rules:
1. Answer based ONLY on the provided context
2. Include specific numbers and dates
3. Reference company ticker and year when citing
4. If info not available, say "I don't have that information"
5. Be concise but thorough
6. For comparisons, use a table format"""

    def generate():
        try:
            from src.retrieval.hybrid import HybridRetriever
            from src.generation.llm_client import OllamaClient
            from src.ml.routing import CostAwareRouter

            llm = OllamaClient()
            retriever = HybridRetriever()

            # Use trained classifier for routing
            router = CostAwareRouter()
            routing_result = router.route(req.query.strip())
            complexity = routing_result.complexity
            model = routing_result.model

            # Retrieve context
            results = retriever.retrieve(req.query.strip(), top_k=5)
            context = _build_context(results, max_chars=2000)

            # Get conversation history for multi-turn context
            history = memory.get_history(limit=10)
            history_text = ""
            if history:
                history_parts = []
                for msg in history:
                    prefix = "User" if msg["role"] == "user" else "Assistant"
                    history_parts.append(f"{prefix}: {msg['content'][:200]}")
                history_text = "\n".join(history_parts)

            # Build messages with multi-turn context
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
            ]

            # Add conversation history if available
            if history_text:
                messages.append({
                    "role": "user",
                    "content": f"Previous conversation:\n{history_text}\n\n---",
                })

            messages.append({
                "role": "user",
                "content": f"Document Context:\n{context}\n\n---\n\nQuestion: {req.query.strip()}\n\nProvide a direct answer based on the context above:",
            })

            # Stream response
            for chunk in llm.chat_stream(model=model, messages=messages):
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            # Send metadata at the end
            citations = []
            seen = set()
            for r in results:
                if r.metadata:
                    ticker = r.metadata.get("ticker", "")
                    year = r.metadata.get("year", "")
                    key = f"{ticker}_{year}"
                    if ticker and key not in seen:
                        seen.add(key)
                        citations.append(f"{ticker} {year}")

            metadata = {
                "type": "metadata",
                "complexity": complexity,
                "model_used": model,
                "citations": citations,
                "cost_usd": routing_result.cost_estimate,
                "steps_count": 3,
            }
            yield f"data: {json.dumps(metadata)}\n\n"

            # Store in conversation memory for multi-turn context
            memory.add_message("user", req.query.strip())
            memory.add_message("assistant", full_text if 'full_text' in dir() else "")
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Upload Endpoints ────────────────────────────────────────────────
@app.get("/app/upload", response_class=HTMLResponse)
def upload_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "upload.html")


@app.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ticker: str = Form(...),
    year: str = Form(...),
):
    """Upload a PDF document for indexing."""
    # Read file
    content = await file.read()
    file_size = len(content)

    # Validate
    valid, msg = validate_upload(file.filename or "unknown.pdf", file_size)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    # Save and process
    doc_id = save_upload(content, file.filename or "document.pdf", ticker, year)

    # Process in background
    background_tasks.add_task(process_upload, doc_id)

    return UploadResponse(
        doc_id=doc_id,
        status="processing",
        filename=file.filename or "document.pdf",
        ticker=ticker.upper(),
        year=year,
    )


@app.get("/upload/status/{doc_id}", response_model=UploadStatus)
def upload_status(doc_id: str) -> UploadStatus:
    """Check upload processing status."""
    status = get_upload_status(doc_id)
    if not status:
        raise HTTPException(status_code=404, detail="Document not found")
    return UploadStatus(
        doc_id=status["doc_id"],
        filename=status["filename"],
        status=status["status"],
        chunk_count=status["chunk_count"],
        error=status.get("error"),
    )


@app.get("/uploads", response_model=list[UploadStatus])
def list_all_uploads() -> list[UploadStatus]:
    """List all uploaded documents."""
    uploads = list_uploads()
    return [
        UploadStatus(
            doc_id=u["doc_id"],
            filename=u["filename"],
            status=u["status"],
            chunk_count=u["chunk_count"],
            error=u.get("error"),
        )
        for u in uploads
    ]


@app.delete("/upload/{doc_id}")
def delete_uploaded(doc_id: str):
    """Delete uploaded document."""
    if not delete_upload(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}


# ── Feedback Endpoints ──────────────────────────────────────────────
@app.post("/feedback")
def feedback(req: FeedbackRequest):
    """Submit feedback for a query response."""
    entry = store_feedback(
        query=req.query,
        answer=req.answer,
        rating=req.rating,
        comment=req.comment,
    )
    return {"status": "stored", "id": entry["id"]}


@app.get("/feedback/stats", response_model=FeedbackStats)
def feedback_stats() -> FeedbackStats:
    """Get aggregated feedback statistics."""
    stats = get_feedback_stats()
    return FeedbackStats(**stats)


@app.get("/feedback/recent")
def feedback_recent(limit: int = 20):
    """Get recent feedback entries."""
    return {"feedback": get_recent_feedback(limit)}


# ── Cost Analytics Endpoints ────────────────────────────────────────
@app.get("/analytics/models")
def model_comparison():
    """Compare performance across models."""
    analytics = CostAnalytics()
    return analytics.model_comparison()


@app.get("/analytics/routing")
def routing_breakdown():
    """Analyze routing efficiency and breakdown."""
    analytics = CostAnalytics()
    return analytics.routing_breakdown()


@app.get("/analytics/trend")
def cost_trend(days: int = 7):
    """Get cost trend over time."""
    analytics = CostAnalytics()
    return analytics.cost_trend(days=days)


@app.get("/analytics/tokens")
def cost_per_token():
    """Analyze cost efficiency per token."""
    analytics = CostAnalytics()
    return analytics.cost_per_token()


@app.get("/app/comparison", response_class=HTMLResponse)
def comparison_page(request: Request) -> HTMLResponse:
    """Model comparison dashboard page."""
    return templates.TemplateResponse(request, "comparison.html")


# ── Export Endpoints ────────────────────────────────────────────────
@app.get("/export/query")
def export_query(
    query: str,
    answer: str,
    model_used: str = "unknown",
    cost_usd: float = 0.0,
    latency_ms: float = 0.0,
    steps_count: int = 0,
):
    """Export a single query result to PDF."""
    exporter = QueryExporter()
    filepath = exporter.export_query_pdf(
        query=query,
        answer=answer,
        citations=[],  # Could be passed as param
        model_used=model_used,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        steps_count=steps_count,
    )
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(filepath),
        filename=filepath.name,
        media_type="application/pdf",
    )


@app.get("/export/analytics")
def export_analytics():
    """Export analytics summary to PDF."""
    analytics = CostAnalytics()
    data = {
        "models": analytics.model_comparison().get("models", []),
        "routing_efficiency": analytics.routing_breakdown().get("routing_efficiency", {}),
    }
    exporter = QueryExporter()
    filepath = exporter.export_analytics_pdf(data)
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(filepath),
        filename=filepath.name,
        media_type="application/pdf",
    )


@app.get("/export/queries/csv")
def export_queries_csv():
    """Export query history to CSV."""
    from src.generation.cost_tracker import CostTracker
    tracker = CostTracker()
    history = tracker.load_history()

    queries = []
    for r in history:
        queries.append({
            "query": r.query,
            "answer": "",  # Not stored in cost tracker
            "model_used": r.model,
            "complexity": r.complexity,
            "cost_usd": r.cost_usd,
            "latency_ms": r.latency_ms,
            "citations": [],
            "timestamp": r.timestamp,
        })

    exporter = QueryExporter()
    filepath = exporter.export_queries_csv(queries)
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(filepath),
        filename=filepath.name,
        media_type="text/csv",
    )


@app.get("/export/list")
def list_exports():
    """List all exported files."""
    exporter = QueryExporter()
    return {"exports": exporter.list_exports()}


# ── Multi-turn Conversation Endpoints ───────────────────────────────
@app.get("/conversation/context")
def conversation_context():
    """Get conversation context string for LLM."""
    context = memory.get_context_string()
    return {"context": context, "history": memory.get_history(limit=10)}


@app.post("/conversation/session")
def create_session(session_id: str):
    """Create or switch to a conversation session."""
    memory.current_session = session_id
    return {"status": "ok", "session_id": session_id}


@app.get("/conversation/sessions")
def list_sessions():
    """List all conversation sessions."""
    return {"sessions": memory.get_session_ids()}


@app.delete("/conversation/session/{session_id}")
def delete_session(session_id: str):
    """Delete a conversation session."""
    if session_id in memory.conversations:
        del memory.conversations[session_id]
    return {"status": "deleted"}


def _build_context(results: list, max_chars: int = 2000) -> str:
    """Build context string from retrieval results."""
    from src.agents.graph import _build_context_from_tools

    # Convert results to context_data format expected by _build_context_from_tools
    context_data = {}
    for r in results:
        ticker = r.metadata.get("ticker", "") if r.metadata else ""
        year = r.metadata.get("year", "") if r.metadata else ""
        if ticker not in context_data:
            context_data[ticker] = []
        context_data[ticker].append({"text": r.text[:500], "ticker": ticker, "year": year})

    return _build_context_from_tools(context_data)
