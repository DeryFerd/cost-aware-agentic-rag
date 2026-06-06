"""FastAPI application for Cost-Aware Agentic RAG."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

# Initialize components
orchestrator = AgenticOrchestrator()
cost_tracker = CostTracker()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    stats = orchestrator.retriever.stats()
    return HealthResponse(
        status="ok",
        vector_store_count=stats["vector_count"],
        bm25_count=stats["bm25_count"],
        version="0.1.0",
    )


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    try:
        response = orchestrator.run(req.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Track cost
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
    summary = cost_tracker.summary()
    return CostSummary(**summary)


@app.get("/cost/budget")
def cost_budget():
    return cost_tracker.budget_check()
