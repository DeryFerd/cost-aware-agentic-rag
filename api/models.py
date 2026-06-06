"""Pydantic models for API request/response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Financial query")
    max_tokens: int = Field(2048, ge=1, le=8192)
    temperature: float = Field(0.1, ge=0.0, le=1.0)


class QueryResponse(BaseModel):
    answer: str
    complexity: str
    model_used: str
    cost_usd: float
    latency_ms: float
    citations: list[str]
    steps_count: int


class DocumentInfo(BaseModel):
    ticker: str
    chunk_count: int
    source_files: list[str]


class EvalResultResponse(BaseModel):
    query_id: str
    faithfulness: float
    relevancy: float
    completeness: float
    overall: float
    issues: list[str]


class CostSummary(BaseModel):
    total_queries: int
    total_cost: float
    avg_cost_per_query: float
    cost_by_model: dict[str, float]
    avg_latency_ms: float


class HealthResponse(BaseModel):
    status: str
    vector_store_count: int
    bm25_count: int
    version: str
