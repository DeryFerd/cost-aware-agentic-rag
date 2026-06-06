"""Main Agentic RAG orchestrator with tool-calling loop."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from src.config import settings
from src.generation.llm_client import OllamaClient, LLMResponse
from src.retrieval.hybrid import HybridRetriever
from src.agents.tools import ToolRegistry

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

        # Clean up response - remove any tool call syntax
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

        # Extract citations from context
        citations = []
        for r in retrieval_results:
            if r.metadata and r.metadata.get("source"):
                citations.append(r.metadata["source"])

        return AgentResponse(
            answer=answer,
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

The relevant document passages have already been retrieved for you. Use ONLY the provided context to answer.

Rules:
1. Answer based ONLY on the provided context
2. Include specific numbers, percentages, and dates in your answers
3. If information is not available in the context, say "I don't have that information in the provided documents"
4. Be concise but thorough — prioritize accuracy over length
5. Do NOT use any tool calls or special syntax — just provide a direct answer
"""
