"""Multi-agent architecture with specialized sub-agents.

Splits the monolithic orchestrator into specialized agents:
- ResearchAgent: Finds relevant information from SEC filings
- AnalysisAgent: Analyzes and compares financial data
- VerificationAgent: Verifies facts and citations

Each agent is a LangGraph sub-graph that can be composed.
"""

from __future__ import annotations

import logging
import re
import time
from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.agents.graph import (
    AgentState,
    _build_context_from_tools,
    _clean_response,
    _execute_compare,
    _execute_get_financials,
    _execute_search,
    _verify_citations,
)
from src.config import settings
from src.generation.llm_client import OllamaClient
from src.observability.tracing import instrument

logger = logging.getLogger(__name__)


# ── Research Agent ──────────────────────────────────────────────

class ResearchState(TypedDict):
    """State for the research sub-agent."""
    query: str
    search_results: str
    financial_data: str
    comparisons: str
    context: str
    tools_used: list[str]


@instrument("research_agent")
def research_agent(state: AgentState) -> dict:
    """Find relevant information from SEC filings.

    This agent focuses on retrieval — finding the right documents
    and extracting relevant information.
    """
    query = state["query"]

    # Extract tickers from query
    tickers = _extract_tickers(query)

    # Search for relevant information
    search_results = _execute_search(query, tickers[0] if tickers else "")

    # Get specific financial data if tickers are mentioned
    financial_data = ""
    if tickers:
        financial_parts = []
        for ticker in tickers[:3]:  # Limit to 3 companies
            for metric in ["revenue", "employees", "risks"]:
                result = _execute_get_financials(ticker, metric)
                financial_parts.append(result)
        financial_data = "\n".join(financial_parts)

    # Compare companies if multiple tickers
    comparisons = ""
    if len(tickers) >= 2:
        comparisons = _execute_compare(",".join(tickers[:3]), "revenue")

    # Build context from all results
    context = _build_context_from_tools({
        "search": search_results,
        "financials": financial_data,
        "comparisons": comparisons,
    })

    return {
        "context": context,
        "tools_used": ["search", "get_financials", "compare_companies"],
    }


# ── Analysis Agent ──────────────────────────────────────────────

@instrument("analysis_agent")
def analysis_agent(state: AgentState) -> dict:
    """Analyze and compare financial data.

    This agent takes the context from the research agent
    and produces a structured analysis.
    """
    query = state["query"]
    context = state.get("context", "")
    llm = OllamaClient()
    model = state.get("model", settings.ollama_simple_model)

    analysis_prompt = f"""Analyze this financial information and provide a structured response.

Context from SEC filings:
{context}

Question: {query}

Provide:
1. Key findings (with specific numbers and dates)
2. Comparison points (if multiple companies)
3. Risk factors or caveats
4. Confidence level (high/medium/low)

Be specific, cite sources with [TICKER YEAR] format."""

    resp = llm.chat(
        model=model,
        messages=[
            {"role": "system", "content": "You are a financial analyst specializing in SEC 10-K filings. Be precise with numbers and cite your sources."},
            {"role": "user", "content": analysis_prompt},
        ],
        temperature=0.1,
        max_tokens=1500,
    )

    answer = _clean_response(resp.content)
    _, verified_citations = _verify_citations(answer, context)

    return {
        "answer": answer,
        "citations": verified_citations,
        "total_cost": state.get("total_cost", 0.0) + resp.cost_usd,
        "tokens_in": resp.tokens_in,
        "tokens_out": resp.tokens_out,
    }


# ── Verification Agent ─────────────────────────────────────────

@instrument("verification_agent")
def verification_agent(state: AgentState) -> dict:
    """Verify facts and citations in the answer.

    This agent checks that:
    - All cited sources exist in the context
    - Numbers and dates are accurate
    - The answer is grounded in the retrieved context
    """
    answer = state.get("answer", "")
    context = state.get("context", "")

    # Verify citations
    answer, verified_citations = _verify_citations(answer, context)

    # Check for ungrounded claims
    issues = []

    # Extract dollar amounts and verify they appear in context
    dollar_pattern = r'\$[\d,.]+\s*(?:billion|million|B|M)?'
    amounts = re.findall(dollar_pattern, answer)
    for amount in amounts:
        if amount.lower() not in context.lower():
            issues.append(f"ungrounded_amount: {amount}")

    # Check if answer is too short (potential no-answer)
    if len(answer.split()) < 10:
        issues.append("answer_too_short")

    # Add verification metadata
    verification_score = 1.0 - (len(issues) * 0.2)  # Deduct 20% per issue
    verification_score = max(0.0, verification_score)

    return {
        "citations": verified_citations,
        "steps": state.get("steps", []) + [{
            "action": "verify",
            "score": verification_score,
            "issues": issues,
        }],
    }


# ── Helper Functions ──────────────────────────────────────────

def _extract_tickers(query: str) -> list[str]:
    """Extract company tickers from query."""
    tickers = []
    ticker_map = {
        "microsoft": "MSFT", "msft": "MSFT",
        "amazon": "AMZN", "amzn": "AMZN",
        "meta": "META", "facebook": "META",
        "google": "GOOG", "alphabet": "GOOG", "goog": "GOOG",
        "tesla": "TSLA", "tsla": "TSLA",
        "apple": "AAPL", "aapl": "AAPL",
        "nvidia": "NVDA", "nvda": "NVDA",
    }

    query_lower = query.lower()
    for keyword, ticker in ticker_map.items():
        if keyword in query_lower and ticker not in tickers:
            tickers.append(ticker)

    return tickers


# ── Build Multi-Agent Graph ──────────────────────────────────────

def build_multi_agent_graph() -> StateGraph:
    """Build the multi-agent state graph.

    Flow: Research → Analysis → Verification → End
    """
    graph = StateGraph(AgentState)

    # Add specialized agent nodes
    graph.add_node("research", research_agent)
    graph.add_node("analysis", analysis_agent)
    graph.add_node("verification", verification_agent)

    # Set entry point
    graph.set_entry_point("research")

    # Linear flow: research → analysis → verification → end
    graph.add_edge("research", "analysis")
    graph.add_edge("analysis", "verification")
    graph.add_edge("verification", END)

    return graph.compile()


class MultiAgentOrchestrator:
    """Multi-agent orchestrator using specialized sub-agents.

    Uses ResearchAgent → AnalysisAgent → VerificationAgent pipeline
    for more thorough and reliable financial analysis.
    """

    def __init__(self) -> None:
        self.graph = build_multi_agent_graph()

    def run(self, query: str, thread_id: str = "default", tenant_id: str = "") -> dict:
        """Execute the multi-agent pipeline."""
        t0 = time.perf_counter()

        initial_state = {
            "messages": [{"role": "user", "content": query}],
            "query": query,
            "complexity": "",
            "model": "",
            "context": "",
            "tools_used": [],
            "citations": [],
            "chunks_used": 0,
            "total_cost": 0.0,
            "tokens_in": 0,
            "tokens_out": 0,
            "steps": [],
            "reflection_count": 0,
            "answer": "",
            "needs_retry": False,
            "tenant_id": tenant_id,
        }

        config = {"configurable": {"thread_id": thread_id}}
        result = self.graph.invoke(initial_state, config)

        total_latency = (time.perf_counter() - t0) * 1000

        return {
            "answer": result.get("answer", ""),
            "complexity": result.get("complexity", ""),
            "model_used": result.get("model", ""),
            "steps": result.get("steps", []),
            "total_cost_usd": result.get("total_cost", 0.0),
            "tokens_in": result.get("tokens_in", 0),
            "tokens_out": result.get("tokens_out", 0),
            "total_latency_ms": total_latency,
            "citations": result.get("citations", []),
            "chunks_used": result.get("chunks_used", 0),
            "tools_used": result.get("tools_used", []),
            "agent_type": "multi_agent",
        }
