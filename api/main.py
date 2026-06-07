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
from src.agents.orchestrator import AgenticOrchestrator
from src.generation.cost_tracker import CostTracker, QueryCostRecord
from src.config import settings

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
orchestrator = AgenticOrchestrator()
cost_tracker = CostTracker()


@app.on_event("startup")
async def startup_event():
    """Load indices on startup."""
    try:
        orchestrator.retriever.load_indices()
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
        stats = orchestrator.retriever.stats()
        return HealthResponse(
            status="ok",
            vector_store_count=stats["vector_count"],
            bm25_count=stats["bm25_count"],
            version="0.1.0",
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        response = orchestrator.run(req.query.strip())
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {e}")

    # Track cost
    try:
        cost_tracker.record(
            QueryCostRecord(
                query=req.query,
                model=response.model_used,
                complexity=response.complexity,
                tokens_in=0,
                tokens_out=0,
                cost_usd=response.total_cost_usd,
                latency_ms=response.total_latency_ms,
            )
        )
    except Exception as e:
        logger.warning(f"Cost tracking failed: {e}")

    return QueryResponse(
        answer=response.answer,
        complexity=response.complexity,
        model_used=response.model_used,
        cost_usd=response.total_cost_usd,
        latency_ms=response.total_latency_ms,
        citations=response.citations,
        steps_count=len(response.steps),
    )


@app.get("/cost/summary", response_model=CostSummary)
def cost_summary() -> CostSummary:
    try:
        summary = cost_tracker.summary()
        return CostSummary(**summary)
    except Exception as e:
        logger.error(f"Cost summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cost summary failed: {e}")


@app.get("/cost/budget")
def cost_budget():
    try:
        return cost_tracker.budget_check()
    except Exception as e:
        logger.error(f"Budget check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Budget check failed: {e}")


@app.post("/query/stream")
def query_stream(req: QueryRequest):
    """Stream response token by token for better UX."""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    import json

    def generate():
        try:
            # Classify complexity
            complexity = orchestrator.llm.classify_complexity(req.query.strip())
            model = orchestrator.llm.select_model(complexity)

            # Retrieve context
            retrieval_results = orchestrator.retriever.retrieve(req.query.strip(), top_k=5)
            context = _build_context(retrieval_results, max_chars=2000)

            # Build messages
            system_prompt = orchestrator._build_system_prompt()
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Document Context:\n{context}\n\n---\n\nQuestion: {req.query.strip()}\n\nProvide a direct answer based on the context above:",
                },
            ]

            # Stream response
            for chunk in orchestrator.llm.chat_stream(model=model, messages=messages):
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            # Send metadata at the end
            citations = orchestrator._extract_relevant_citations(req.query.strip(), retrieval_results)
            metadata = {
                "type": "metadata",
                "complexity": complexity,
                "model_used": model,
                "citations": citations,
                "cost_usd": 0.0,
                "steps_count": 3,
            }
            yield f"data: {json.dumps(metadata)}\n\n"
            yield f"data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _build_context(results: list, max_chars: int = 2000) -> str:
    """Build context string from retrieval results."""
    from src.agents.orchestrator import _build_context as build_ctx
    return build_ctx(results, max_chars)
