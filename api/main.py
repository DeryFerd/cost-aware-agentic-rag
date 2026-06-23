"""FastAPI application for Cost-Aware Agentic RAG."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.middleware import TraceIDMiddleware
from api.models import HealthResponse
from api.routes.admin import router as admin_router
from api.routes.analytics import router as analytics_router
from api.routes.compare import router as compare_router
from api.routes.documents import router as documents_router
from api.routes.failure_analysis import router as failure_router
from api.routes.feedback import router as feedback_router
from api.routes.knowledge import router as knowledge_router
from api.routes.query import router as query_router
from api.routes.upload import router as upload_router
from src.config import settings
from src.database.admin_auth import init_admin
from src.observability.tracing import setup_tracing

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

_startup_time = time.perf_counter()

app = FastAPI(
    title="Cost-Aware Agentic RAG",
    description="Production-shaped Agentic RAG prototype for SEC 10-K Financial Analysis",
    version="0.1.0",
)

app.add_middleware(TraceIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
web_dir = project_root / "web"
app.mount("/static", StaticFiles(directory=str(web_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(web_dir / "templates"))


@app.on_event("startup")
async def startup_event():
    """Initialize admin user and tracing on startup.

    Index loading is deferred to first query for fast startup.
    """
    setup_tracing()
    init_admin()
    logger.info("Startup complete in %.1fs", time.perf_counter() - _startup_time)

    # FastAPI OTel middleware (if opentelemetry-instrumentation-fastapi is installed)
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI OTel middleware attached")
    except ImportError:
        pass


# ── Register Routers ────────────────────────────────────────────────
app.include_router(query_router)
app.include_router(upload_router)
app.include_router(documents_router)
app.include_router(feedback_router)
app.include_router(analytics_router)
app.include_router(admin_router)
app.include_router(compare_router)
app.include_router(knowledge_router)
app.include_router(failure_router)


# ── Page Routes ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@app.get("/app", response_class=HTMLResponse)
async def dashboard_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "app.html")


@app.get("/app/documents", response_class=HTMLResponse)
async def documents_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "documents.html")


@app.get("/app/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "analytics.html")


@app.get("/app/upload", response_class=HTMLResponse)
async def upload_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "upload.html")


@app.get("/app/comparison", response_class=HTMLResponse)
async def comparison_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "comparison.html")


@app.get("/app/admin", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin.html")


@app.get("/app/latency", response_class=HTMLResponse)
async def latency_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "latency.html")


@app.get("/app/cost-optimization", response_class=HTMLResponse)
async def cost_optimization_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "cost_optimization.html")


@app.get("/app/failures", response_class=HTMLResponse)
async def failures_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "failures.html")


# ── Health Check ─────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    doc_count = 0
    if settings.raw_dir.exists():
        for company_dir in settings.raw_dir.iterdir():
            if company_dir.is_dir():
                for year_dir in company_dir.iterdir():
                    if year_dir.is_dir():
                        for _f in year_dir.glob("*.txt"):
                            doc_count += 1

    chunk_count = 0
    try:
        from src.retrieval.vector_store import VectorStore
        vs = VectorStore()
        chunk_count = vs.count()
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        document_count=doc_count,
        chunk_count=chunk_count,
        version="0.1.0",
    )
