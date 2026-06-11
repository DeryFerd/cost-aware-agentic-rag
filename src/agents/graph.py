"""LangGraph-based agentic RAG orchestrator with state graph."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from src.config import settings
from src.generation.llm_client import OllamaClient
from src.retrieval.hybrid import HybridRetriever
from src.agents.memory import memory
from src.multimodal.tables import extract_tables_from_text, format_table_for_context

logger = logging.getLogger(__name__)


# ── State Definition ──────────────────────────────────────────────

class AgentState(TypedDict):
    """State for the agentic RAG graph."""
    messages: Annotated[list, add_messages]
    query: str
    complexity: str
    model: str
    context: str
    tools_used: list[str]
    citations: list[str]
    chunks_used: int
    total_cost: float
    steps: list[dict]
    reflection_count: int
    answer: str
    needs_retry: bool


# ── Tool Definitions ──────────────────────────────────────────────

def _build_retriever():
    """Build hybrid retriever (lazy)."""
    return HybridRetriever()


def _execute_search(query: str, ticker: str = "") -> str:
    """Execute search tool."""
    retriever = _build_retriever()
    results = retriever.retrieve(query, top_k=5, use_filters=bool(ticker))
    return json.dumps([
        {
            "text": r.text[:500],
            "score": round(r.score, 3),
            "ticker": r.metadata.get("ticker", "") if r.metadata else "",
            "year": r.metadata.get("year", "") if r.metadata else "",
        }
        for r in results
    ])


def _execute_get_financials(ticker: str, metric: str, year: str = "") -> str:
    """Execute get_financials tool."""
    retriever = _build_retriever()
    query = f"{ticker} {metric}"
    if year:
        query += f" {year}"
    results = retriever.retrieve(query, top_k=3, use_filters=True)
    return json.dumps([
        {"text": r.text[:500], "ticker": r.metadata.get("ticker", "") if r.metadata else ""}
        for r in results
    ])


def _execute_compare(tickers: str, metric: str) -> str:
    """Execute compare_companies tool."""
    retriever = _build_retriever()
    all_results = []
    for ticker in tickers.split(","):
        ticker = ticker.strip()
        if ticker:
            results = retriever.retrieve(f"{ticker} {metric}", top_k=2, use_filters=True)
            for r in results:
                year = r.metadata.get("year", "") if r.metadata else ""
                all_results.append({"text": r.text[:400], "ticker": ticker, "year": year})
    return json.dumps(all_results)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search SEC 10-K documents for information about a company or topic",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "ticker": {"type": "string", "description": "Company ticker (optional): MSFT, AMZN, META, GOOG, TSLA, AAPL, NVDA"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financials",
            "description": "Get specific financial metrics for a company",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Company ticker"},
                    "metric": {"type": "string", "description": "Metric: revenue, employees, risks, description"},
                    "year": {"type": "string", "description": "Year (optional)"},
                },
                "required": ["ticker", "metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_companies",
            "description": "Compare metrics between multiple companies",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {"type": "string", "description": "Comma-separated tickers"},
                    "metric": {"type": "string", "description": "Metric to compare: revenue, employees, risks"},
                },
                "required": ["tickers", "metric"],
            },
        },
    },
]


# ── Graph Nodes ───────────────────────────────────────────────────

def planner_node(state: AgentState) -> dict:
    """Plan which tools to use for the query."""
    from src.ml.routing import CostAwareRouter

    query = state["query"]

    # Use trained classifier for routing (not keyword matching)
    router = CostAwareRouter()
    routing_result = router.route(query)
    complexity = routing_result.complexity
    model = routing_result.model

    llm = OllamaClient()

    plan_prompt = f"""Analyze this financial query and decide which tools to use.

Available tools:
- search: Search SEC 10-K documents
- get_financials: Get specific financial metrics
- compare_companies: Compare metrics between companies

Query: {query}

Respond with a JSON plan:
{{
    "tools": [{{"tool": "tool_name", "args": {{"param": "value"}}}}],
    "reasoning": "Why these tools"
}}
Only use tools that are needed."""

    resp = llm.chat(
        model=model,
        messages=[{"role": "user", "content": plan_prompt}],
        temperature=0.0,
        max_tokens=500,
        tools=TOOLS,
    )

    # Parse tool calls from response
    tool_calls = []
    try:
        json_match = re.search(r'\{.*\}', resp.content, re.DOTALL)
        if json_match:
            plan = json.loads(json_match.group())
            tool_calls = plan.get("tools", [])
    except json.JSONDecodeError:
        pass

    # Fallback: default to search
    if not tool_calls:
        tool_calls = [{"tool": "search", "args": {"query": query}}]

    return {
        "complexity": complexity,
        "model": model,
        "steps": state.get("steps", []) + [{"action": "plan", "model": model, "tools": [t["tool"] for t in tool_calls]}],
        "messages": [{"role": "assistant", "content": f"Planning to use tools: {[t['tool'] for t in tool_calls]}"}],
    }


def tool_executor_node(state: AgentState) -> dict:
    """Execute the planned tools and build context."""
    llm = OllamaClient()
    query = state["query"]
    model = state["model"]

    # Re-plan with tool calling enabled
    plan_prompt = f"""Analyze this financial query and decide which tools to use.

Query: {query}

Use the available tools to gather information."""

    resp = llm.chat(
        model=model,
        messages=[{"role": "user", "content": plan_prompt}],
        temperature=0.0,
        max_tokens=500,
        tools=TOOLS,
    )

    # Execute tool calls
    context_data = {}
    tools_used = []
    steps = list(state.get("steps", []))

    # Check if response has tool calls
    msg = resp.raw.get("message", {})
    if "tool_calls" in msg:
        for tc in msg["tool_calls"]:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            args = func.get("arguments", {})

            if tool_name == "search":
                result = _execute_search(args.get("query", query), args.get("ticker", ""))
            elif tool_name == "get_financials":
                result = _execute_get_financials(args.get("ticker", ""), args.get("metric", ""), args.get("year", ""))
            elif tool_name == "compare_companies":
                result = _execute_compare(args.get("tickers", ""), args.get("metric", ""))
            else:
                result = f"Unknown tool: {tool_name}"

            context_data[tool_name] = result
            tools_used.append(tool_name)
            steps.append({"action": "tool_call", "tool": tool_name, "args": args, "output": result[:200]})
    else:
        # No tool calls - use search as fallback
        result = _execute_search(query)
        context_data["search"] = result
        tools_used.append("search")
        steps.append({"action": "tool_call", "tool": "search", "args": {"query": query}, "output": result[:200]})

    # Build context from tool results
    context = _build_context_from_tools(context_data)

    return {
        "context": context,
        "tools_used": tools_used,
        "steps": steps,
        "chunks_used": sum(1 for v in context_data.values() if isinstance(v, str)),
    }


def generator_node(state: AgentState) -> dict:
    """Generate answer using context from tools."""
    llm = OllamaClient()
    query = state["query"]
    model = state["model"]
    context = state["context"]
    conv_context = memory.get_context_string()

    system_prompt = """You are a financial analyst AI specializing in SEC 10-K filings.

Rules:
1. Answer based ONLY on the provided context
2. Include specific numbers and dates
3. Reference company ticker and year when citing
4. If info not available, say "I don't have that information"
5. Be concise but thorough
6. For comparisons, use a table format"""

    user_content = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
    if conv_context:
        user_content = f"Previous conversation:\n{conv_context}\n\n{user_content}"

    resp = llm.chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )

    answer = _clean_response(resp.content)
    citations = _extract_citations(query, context)

    # Add to memory
    memory.add_message("user", query)
    memory.add_message("assistant", answer, metadata={
        "complexity": state.get("complexity", ""),
        "model": model,
        "tools_used": state.get("tools_used", []),
    })

    return {
        "answer": answer,
        "citations": citations,
        "steps": state.get("steps", []) + [{"action": "respond", "model": model}],
        "messages": [{"role": "assistant", "content": answer}],
    }


def reflector_node(state: AgentState) -> dict:
    """Self-reflect on answer quality."""
    llm = OllamaClient()
    query = state["query"]
    answer = state.get("answer", "")
    reflection_count = state.get("reflection_count", 0)

    if reflection_count >= 2:
        return {"reflection_count": reflection_count, "needs_retry": False}

    prompt = f"""Evaluate this answer to a financial query.

Query: {query}
Answer: {answer}

Is this answer complete, accurate, and well-sourced?
Respond with JSON:
{{"needs_improvement": true/false, "issues": ["issue1"], "missing_info": "what's missing"}}"""

    resp = llm.chat(
        model=settings.ollama_simple_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=300,
    )

    try:
        json_match = re.search(r'\{.*\}', resp.content, re.DOTALL)
        if json_match:
            reflection = json.loads(json_match.group())
            if reflection.get("needs_improvement"):
                return {
                    "reflection_count": reflection_count + 1,
                    "needs_retry": True,
                    "steps": state.get("steps", []) + [{"action": "reflect", "issues": reflection.get("issues", [])}],
                }
    except json.JSONDecodeError:
        pass

    return {"reflection_count": reflection_count, "needs_retry": False}


def should_continue(state: AgentState) -> str:
    """Decide whether to continue reflecting or end."""
    # Stop after max reflections
    if state.get("reflection_count", 0) >= 2:
        return "end"
    # Stop if we have a good answer (no issues found by reflector)
    if state.get("answer") and not state.get("needs_retry"):
        return "end"
    # Continue to tools if retry is needed
    return "tools"


# ── Helper Functions ──────────────────────────────────────────────

def _clean_response(text: str) -> str:
    """Remove tool_call syntax and other artifacts from model output."""
    text = re.sub(r'```tool_code.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'<tool_call>.*?</tool_call>', '', text, flags=re.DOTALL)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _build_context_from_tools(context_data: dict) -> str:
    """Build context string from tool results."""
    parts = []
    all_tables = []

    for tool_name, result_str in context_data.items():
        try:
            results = json.loads(result_str) if isinstance(result_str, str) else result_str
        except json.JSONDecodeError:
            results = [{"text": result_str, "ticker": "", "year": ""}]

        if isinstance(results, list):
            for r in results:
                if isinstance(r, dict):
                    ticker = r.get("ticker", "")
                    year = r.get("year", "")
                    text = r.get("text", "")
                    parts.append(f"[{ticker} {year}] {text}")

                    tables = extract_tables_from_text(text, ticker, year)
                    all_tables.extend(tables)

    if all_tables:
        table_context = format_table_for_context(all_tables[:3])
        if table_context:
            parts.append(f"\nStructured Data:\n{table_context}")

    return "\n\n---\n\n".join(parts[:10])


def _extract_citations(query: str, context: str | dict) -> list[str]:
    """Extract relevant citations from context (str or dict)."""
    query_lower = query.lower()
    mentioned = set()

    company_keywords = {
        "MSFT": ["microsoft", "msft"],
        "AMZN": ["amazon", "amzn"],
        "META": ["meta", "facebook"],
        "GOOG": ["google", "alphabet", "goog"],
        "TSLA": ["tesla", "tsla"],
        "AAPL": ["apple", "aapl"],
        "NVDA": ["nvidia", "nvda"],
    }

    for ticker, keywords in company_keywords.items():
        for kw in keywords:
            if kw in query_lower:
                mentioned.add(ticker)
                break

    citations = []
    seen = set()

    # Handle string context (parse from text)
    if isinstance(context, str):
        import re
        # Extract ticker-year patterns from context text
        pattern = r'\[([A-Z]{2,5})\s+(\d{4})\]'
        for match in re.finditer(pattern, context):
            ticker, year = match.groups()
            key = f"{ticker}_{year}"
            if key not in seen:
                if not mentioned or ticker in mentioned:
                    seen.add(key)
                    citations.append(f"{ticker} {year}")
        return citations[:5]

    # Handle dict context (original format)
    for tool_name, result_str in context.items():
        try:
            results = json.loads(result_str) if isinstance(result_str, str) else result_str
        except json.JSONDecodeError:
            continue

        if isinstance(results, list):
            for r in results:
                if isinstance(r, dict):
                    ticker = r.get("ticker", "")
                    year = r.get("year", "")
                    key = f"{ticker}_{year}"
                    if ticker and key not in seen:
                        if not mentioned or ticker in mentioned:
                            seen.add(key)
                            citations.append(f"{ticker} {year}")

    return citations[:5]


# ── Build Graph ───────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build the LangGraph state graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("tools", tool_executor_node)
    graph.add_node("generator", generator_node)
    graph.add_node("reflector", reflector_node)

    # Set entry point
    graph.set_entry_point("planner")

    # Add edges
    graph.add_edge("planner", "tools")
    graph.add_edge("tools", "generator")
    graph.add_edge("generator", "reflector")
    graph.add_conditional_edges(
        "reflector",
        should_continue,
        {
            "end": END,
            "tools": "tools",
        },
    )

    return graph.compile(checkpointer=MemorySaver())


# ── Public API ────────────────────────────────────────────────────

class LangGraphOrchestrator:
    """LangGraph-based agentic orchestrator."""

    def __init__(self) -> None:
        self.graph = build_graph()

    def run(self, query: str, thread_id: str = "default") -> dict:
        """Execute the agentic loop using LangGraph."""
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
            "steps": [],
            "reflection_count": 0,
            "answer": "",
            "needs_retry": False,
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
            "total_latency_ms": total_latency,
            "citations": result.get("citations", []),
            "chunks_used": result.get("chunks_used", 0),
            "tools_used": result.get("tools_used", []),
        }
