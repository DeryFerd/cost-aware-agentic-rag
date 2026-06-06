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
        logger.info(f"Query classified as '{complexity}' → model: {model}")

        steps.append(
            AgentStep(step=1, action="route", model=model, cost_usd=0.0)
        )

        # Step 2: Build messages for agent
        system_prompt = self._build_system_prompt()
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        # Step 3: Tool-calling loop
        collected_citations: list[str] = []
        collected_context: list[str] = []

        for iteration in range(settings.max_iterations):
            resp = self.llm.chat(
                model=model,
                messages=messages,
                tools=self.tools.get_tool_schemas(),
            )
            total_cost += resp.cost_usd

            msg = resp.raw.get("message", {})
            tool_calls = msg.get("tool_calls", [])

            if not tool_calls:
                # Agent decided to respond directly
                steps.append(
                    AgentStep(
                        step=iteration + 2,
                        action="respond",
                        model=model,
                        cost_usd=resp.cost_usd,
                        latency_ms=resp.latency_ms,
                    )
                )
                break

            # Execute each tool call
            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                tool_args = fn.get("arguments", {})

                logger.info(f"  Tool call: {tool_name}({tool_args})")

                tool_result = self.tools.execute(tool_name, tool_args)

                steps.append(
                    AgentStep(
                        step=iteration + 2,
                        action="tool_call",
                        tool=tool_name,
                        tool_input=str(tool_args),
                        tool_output=str(tool_result)[:200],
                        model=model,
                        cost_usd=resp.cost_usd,
                        latency_ms=resp.latency_ms,
                    )
                )

                # Collect context and citations
                if tool_name == "retrieve":
                    collected_context.append(str(tool_result))
                if tool_name == "cite":
                    collected_citations.append(str(tool_result))

                # Feed tool result back to agent
                messages.append({"role": "tool", "content": str(tool_result)})

        # Step 4: Final response
        if steps[-1].action != "respond":
            # Force a final response if loop ended without one
            final_resp = self.llm.chat(
                model=model,
                messages=messages + [
                    {
                        "role": "user",
                        "content": (
                            "Based on the information gathered, provide your final "
                            "answer now. Include specific numbers and citations."
                        ),
                    }
                ],
            )
            total_cost += final_resp.cost_usd
            answer = final_resp.content
        else:
            answer = steps[-1].tool_output or ""

        total_latency = (time.perf_counter() - t0) * 1000

        return AgentResponse(
            answer=answer,
            complexity=complexity,
            model_used=model,
            steps=steps,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            citations=collected_citations,
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
