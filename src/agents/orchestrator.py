"""Main Agentic RAG orchestrator with tool-calling loop."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from src.config import settings
from src.generation.llm_client import OllamaClient
from src.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)


def _clean_response(text: str) -> str:
    """Remove tool_call syntax and other artifacts from model output."""
    # Remove ```tool_code blocks
    text = re.sub(r'```tool_code.*?```', '', text, flags=re.DOTALL)
    # Remove tool_call patterns
    text = re.sub(r'<tool_call>.*?</tool_call>', '', text, flags=re.DOTALL)
    # Remove stray tool references
    text = re.sub(r'retrieve\(.*?\)', '', text)
    text = re.sub(r'summarize\(.*?\)', '', text)
    text = re.sub(r'compare\(.*?\)', '', text)
    text = re.sub(r'cite\(.*?\)', '', text)
    # Clean up extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _build_context(results: list, max_chars: int = 2000) -> str:
    """Build context string from retrieval results."""
    context_parts = []
    total_chars = 0

    for r in results:
        text = r.text[:600]  # Limit each chunk
        ticker = r.metadata.get("ticker", "UNKNOWN") if r.metadata else "UNKNOWN"
        year = r.metadata.get("year", "UNKNOWN") if r.metadata else "UNKNOWN"
        section = r.metadata.get("section", "unknown") if r.metadata else "unknown"

        formatted = f"[{ticker} {year} - {section}]\n{text}"
        if total_chars + len(formatted) > max_chars:
            break
        context_parts.append(formatted)
        total_chars += len(formatted)

    return "\n\n---\n\n".join(context_parts)


@dataclass
class AgentStep:
    step: int
    action: str  # "route" | "retrieve" | "respond"
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
    chunks_used: int = 0


class AgenticOrchestrator:
    """Main agent loop: classify → retrieve → generate."""

    def __init__(self) -> None:
        self.llm = OllamaClient()
        self.retriever = HybridRetriever()

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

        # Step 2: Retrieve relevant context (with automatic filtering)
        retrieval_results = self.retriever.retrieve(query, top_k=5)
        context = _build_context(retrieval_results, max_chars=2000)
        logger.info(f"Retrieved {len(retrieval_results)} passages")

        steps.append(
            AgentStep(
                step=2,
                action="retrieve",
                tool="hybrid_search",
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
                "content": f"Document Context:\n{context}\n\n---\n\nQuestion: {query}\n\nProvide a direct answer based on the context above:",
            },
        ]

        resp = self.llm.chat(model=model, messages=messages)
        total_cost += resp.cost_usd

        # Clean up response
        answer = _clean_response(resp.content)

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

        # Extract citations
        citations = []
        for r in retrieval_results:
            if r.metadata:
                ticker = r.metadata.get("ticker", "")
                year = r.metadata.get("year", "")
                if ticker and year:
                    citations.append(f"{ticker} {year}")

        return AgentResponse(
            answer=answer,
            complexity=complexity,
            model_used=model,
            steps=steps,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            citations=list(set(citations)),
            chunks_used=len(retrieval_results),
        )

    def _build_system_prompt(self) -> str:
        return """You are a financial analyst AI specializing in SEC 10-K filings.

Your job is to answer questions about public companies using their 10-K reports.

The relevant document passages have already been retrieved for you. Use ONLY the provided context to answer.

Rules:
1. Answer based ONLY on the provided context — do not make up information
2. Include specific numbers, percentages, and dates when available
3. Reference the company ticker and year when citing information
4. If the context doesn't contain enough information, say "I don't have that information in the provided documents"
5. Be concise — prioritize accuracy over length
6. Do NOT use any tool calls or special syntax — just provide a direct answer
"""
