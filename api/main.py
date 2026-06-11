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

from api.models import (
    QueryRequest,
    QueryResponse,
    CostSummary,
    HealthResponse,
)
from src.agents.graph import LangGraphOrchestrator
from src.generation.cost_tracker import CostTracker, QueryCostRecord
from src.agents.memory import memory
from src.agents.guardrails import guardrails
from src.config import settings
from src.database.cache import cache

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

            # Build messages
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Document Context:\n{context}\n\n---\n\nQuestion: {req.query.strip()}\n\nProvide a direct answer based on the context above:",
                },
            ]

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
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


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
