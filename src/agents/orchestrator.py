"""Main Agentic RAG orchestrator with tool-calling loop."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.config import settings
from src.generation.llm_client import OllamaClient, LLMResponse
from src.retrieval.hybrid import HybridRetriever
from src.agents.tools import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    step: int
    action: str  # "route" | "tool_call" | "respond"
    tool: str | None = None
    tool_input: str | None = None
    tool_output: str | None = None
    model: str = ""
    cost_usd: float = 0.0
    latency_ms: float = 0.0


@dataclass
class AgentResponse:
    answer: str
    complexity: str
    model_used: str
    steps: list[AgentStep] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    citations: list[str] = field(default_factory=list)


class AgenticOrchestrator:
    """Tool-calling agent that reasons over retrieved documents."""

    def __init__(self) -> None:
        self.llm = OllamaClient()
        self.retriever = HybridRetriever()
        self.tools = ToolRegistry(self.retriever, self.llm)

    def run(self, query: str) -> AgentResponse:
        """Execute the full agent loop."""
        t0 = time.perf_counter()
        steps: list[AgentStep] = []
        total_cost = 0.0

        # Step 1: Classify complexity and select model
        complexity = self.llm.classify_complexity(query)
        model = self.llm.select_model(complexity)
        logger.info(f"Query classified as '{complexity}' -> model: {model}")

        steps.append(
            AgentStep(step=1, action="route", model=model, cost_usd=0.0)
        )

        # Step 2: Retrieve relevant context
        retrieval_results = self.retriever.retrieve(query, top_k=5)
        context = "\n\n".join([r.text[:500] for r in retrieval_results])
        logger.info(f"Retrieved {len(retrieval_results)} passages")

        steps.append(
            AgentStep(
                step=2,
                action="tool_call",
                tool="retrieve",
                tool_input=query,
                tool_output=f"{len(retrieval_results)} passages retrieved",
                model=model,
            )
        )

        # Step 3: Generate answer with context
        system_prompt = self._build_system_prompt()
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer based on the context above:",
            },
        ]

        resp = self.llm.chat(
            model=model,
            messages=messages,
        )
        total_cost += resp.cost_usd

        steps.append(
            AgentStep(
                step=3,
                action="respond",
                model=model,
                cost_usd=resp.cost_usd,
                latency_ms=resp.latency_ms,
            )
        )

        total_latency = (time.perf_counter() - t0) * 1000

        # Extract citations from context
        citations = []
        for r in retrieval_results:
            if r.metadata and r.metadata.get("source"):
                citations.append(r.metadata["source"])

        return AgentResponse(
            answer=resp.content,
            complexity=complexity,
            model_used=model,
            steps=steps,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            citations=list(set(citations)),
        )

    def _build_system_prompt(self) -> str:
        return """You are a financial analyst AI specializing in SEC 10-K filings.

Your job is to answer questions about public companies using their 10-K reports.

Available tools:
- retrieve: Search the knowledge base for relevant document passages
- summarize: Summarize multiple passages into a concise answer
- compare: Compare financial metrics across companies or years
- cite: Extract specific citations with page numbers

Rules:
1. Always use the 'retrieve' tool first to find relevant information
2. For comparison questions, use 'compare' after retrieving data
3. Include specific numbers, percentages, and dates in your answers
4. Always cite your sources using the 'cite' tool
5. If information is not available, say so clearly
6. Be concise but thorough — prioritize accuracy over length
"""
