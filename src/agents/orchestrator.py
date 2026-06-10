"""True Agentic RAG orchestrator with tool calling and multi-step reasoning."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from src.config import settings
from src.generation.llm_client import OllamaClient
from src.retrieval.hybrid import HybridRetriever
from src.agents.memory import memory
from src.multimodal.tables import extract_tables_from_text, format_table_for_context

logger = logging.getLogger(__name__)


def _clean_response(text: str) -> str:
    """Remove tool_call syntax and other artifacts from model output."""
    text = re.sub(r'```tool_code.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'<tool_call>.*?</tool_call>', '', text, flags=re.DOTALL)
    text = re.sub(r'retrieve\(.*?\)', '', text)
    text = re.sub(r'summarize\(.*?\)', '', text)
    text = re.sub(r'compare\(.*?\)', '', text)
    text = re.sub(r'cite\(.*?\)', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _build_context(results: list, max_chars: int = 2000) -> str:
    """Build context string from retrieval results."""
    context_parts = []
    total_chars = 0

    for r in results:
        text = r.text[:600]
        ticker = r.metadata.get("ticker", "UNKNOWN") if r.metadata else "UNKNOWN"
        year = r.metadata.get("year", "UNKNOWN") if r.metadata else "UNKNOWN"
        section = r.metadata.get("section", "unknown") if r.metadata else "unknown"

        formatted = f"[{ticker} {year} - {section}]\n{text}"
        if total_chars + len(formatted) > max_chars:
            break
        context_parts.append(formatted)
        total_chars += len(formatted)

    return "\n\n---\n\n".join(context_parts)


# ── Tool Definitions ──────────────────────────────────────────────

TOOLS = {
    "search": {
        "description": "Search SEC 10-K documents for information about a company or topic",
        "parameters": {
            "query": {"type": "string", "description": "Search query"},
            "ticker": {"type": "string", "description": "Company ticker (optional): MSFT, AMZN, META, GOOG, TSLA"},
        },
    },
    "get_financials": {
        "description": "Get specific financial metrics (revenue, employees, etc.) for a company",
        "parameters": {
            "ticker": {"type": "string", "description": "Company ticker: MSFT, AMZN, META, GOOG, TSLA"},
            "metric": {"type": "string", "description": "Metric to get: revenue, employees, risks, description"},
            "year": {"type": "string", "description": "Year (optional): 2022, 2023, 2024"},
        },
    },
    "compare_companies": {
        "description": "Compare metrics between multiple companies",
        "parameters": {
            "tickers": {"type": "string", "description": "Comma-separated tickers: MSFT,AMZN,META"},
            "metric": {"type": "string", "description": "Metric to compare: revenue, employees, risks"},
        },
    },
    "calculate": {
        "description": "Perform calculations on financial data",
        "parameters": {
            "expression": {"type": "string", "description": "Math expression, e.g. '245.1 / 211.9' or 'growth rate from 211.9 to 245.1'"},
        },
    },
    "analyze_image": {
        "description": "Analyze an image (chart, graph, table) and extract data from it",
        "parameters": {
            "image_path": {"type": "string", "description": "Path to the image file"},
            "question": {"type": "string", "description": "What to analyze (optional)"},
        },
    },
}


@dataclass
class AgentStep:
    step: int
    action: str  # "plan" | "tool_call" | "reflect" | "respond"
    tool: str | None = None
    tool_input: dict | None = None
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
    tools_used: list[str] = field(default_factory=list)


class AgenticOrchestrator:
    """True agentic loop: plan → execute tools → reflect → respond."""

    def __init__(self) -> None:
        self.llm = OllamaClient()
        self.retriever = HybridRetriever()

    def run(self, query: str) -> AgentResponse:
        """Execute the full agentic loop."""
        t0 = time.perf_counter()
        steps: list[AgentStep] = []
        total_cost = 0.0
        tools_used = []

        # Add user message to memory
        memory.add_message("user", query)

        # Get conversation context
        conv_context = memory.get_context_string()

        # Step 1: Classify complexity
        complexity = self.llm.classify_complexity(query)
        model = self.llm.select_model(complexity)
        logger.info(f"Query classified as '{complexity}' -> model: {model}")

        steps.append(AgentStep(step=1, action="plan", model=model))

        # Step 2: Plan - decide what tools to use
        plan = self._plan(query, model)
        logger.info(f"Plan: {plan}")

        steps.append(AgentStep(
            step=2,
            action="plan",
            tool_output=json.dumps(plan),
            model=model,
        ))

        # Step 3: Execute tools based on plan
        context_data = {}
        for i, tool_call in enumerate(plan.get("tools", [])):
            tool_name = tool_call["tool"]
            tool_args = tool_call["args"]

            tool_result = self._execute_tool(tool_name, tool_args)
            context_data[tool_name] = tool_result
            tools_used.append(tool_name)

            steps.append(AgentStep(
                step=3 + i,
                action="tool_call",
                tool=tool_name,
                tool_input=tool_args,
                tool_output=str(tool_result)[:200],
                model=model,
            ))

        # Step 4: Build context from tool results
        context = self._build_context_from_tools(context_data)

        # Step 5: Generate answer
        answer = self._generate_answer(query, context, model, conv_context)

        steps.append(AgentStep(
            step=10,
            action="respond",
            model=model,
        ))

        # Step 6: Self-reflect - is the answer good enough?
        reflection = self._reflect(query, answer, context)
        logger.info(f"Reflection: {reflection}")

        # If answer needs improvement, regenerate with more context
        if reflection.get("needs_improvement"):
            more_context = self._retrieve_more(query, reflection.get("missing_info", ""))
            context = context + "\n\n---\n\nAdditional Context:\n" + more_context
            answer = self._generate_answer(query, context, model, conv_context)

            steps.append(AgentStep(
                step=11,
                action="reflect",
                tool_output=f"Improved: {reflection.get('issues', [])}",
                model=model,
            ))

        total_latency = (time.perf_counter() - t0) * 1000

        # Extract citations
        citations = self._extract_citations(query, context_data)

        # Add assistant response to memory
        memory.add_message("assistant", answer, metadata={
            "complexity": complexity,
            "model": model,
            "tools_used": tools_used,
        })

        return AgentResponse(
            answer=answer,
            complexity=complexity,
            model_used=model,
            steps=steps,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            citations=citations,
            chunks_used=sum(len(v) if isinstance(v, list) else 1 for v in context_data.values()),
            tools_used=tools_used,
        )

    def _plan(self, query: str, model: str) -> dict:
        """Plan what tools to use for the query."""
        prompt = f"""Analyze this financial query and decide which tools to use.

Available tools:
{json.dumps(TOOLS, indent=2)}

Query: {query}

Respond with a JSON plan like:
{{
    "tools": [
        {{"tool": "tool_name", "args": {{"param": "value"}}}}
    ],
    "reasoning": "Why these tools"
}}

Only use tools that are needed. For simple factual queries, one tool is enough.
For comparison queries, use compare_companies.
For complex analysis, use multiple tools."""

        resp = self.llm.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )

        # Parse JSON from response
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', resp.content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # Fallback: default plan using search
        return {
            "tools": [{"tool": "search", "args": {"query": query}}],
            "reasoning": "Default to search"
        }

    def _execute_tool(self, tool_name: str, args: dict) -> Any:
        """Execute a tool and return results."""
        if tool_name == "search":
            query = args.get("query", "")
            ticker = args.get("ticker")
            results = self.retriever.retrieve(query, top_k=5, use_filters=bool(ticker))
            return [
                {
                    "text": r.text[:500],
                    "score": round(r.score, 3),
                    "ticker": r.metadata.get("ticker", "") if r.metadata else "",
                    "year": r.metadata.get("year", "") if r.metadata else "",
                }
                for r in results
            ]

        elif tool_name == "get_financials":
            ticker = args.get("ticker", "")
            metric = args.get("metric", "revenue")
            year = args.get("year", "")

            query = f"{ticker} {metric}"
            if year:
                query += f" {year}"

            results = self.retriever.retrieve(query, top_k=3, use_filters=True)
            return [
                {"text": r.text[:500], "ticker": r.metadata.get("ticker", "") if r.metadata else ""}
                for r in results
            ]

        elif tool_name == "compare_companies":
            tickers = args.get("tickers", "").split(",")
            metric = args.get("metric", "revenue")

            all_results = []
            for ticker in tickers:
                ticker = ticker.strip()
                if ticker:
                    results = self.retriever.retrieve(f"{ticker} {metric}", top_k=2, use_filters=True)
                    for r in results:
                        year = r.metadata.get("year", "") if r.metadata else ""
                        all_results.append({
                            "text": r.text[:400],
                            "ticker": ticker,
                            "year": year,
                        })
            return all_results

        elif tool_name == "calculate":
            expression = args.get("expression", "")
            # Simple calculation - just return the expression for now
            return f"Calculation requested: {expression}"

        elif tool_name == "analyze_image":
            image_path = args.get("image_path", "")
            question = args.get("question", "Describe this image and extract any data points.")

            from src.multimodal.vision import VisionAnalyzer
            analyzer = VisionAnalyzer()
            analysis = analyzer.analyze_image(image_path, question)

            return {
                "description": analysis.description,
                "data_points": analysis.data_points,
                "chart_type": analysis.chart_type,
                "insights": analysis.insights,
            }

        return f"Unknown tool: {tool_name}"

    def _build_context_from_tools(self, context_data: dict) -> str:
        """Build context string from tool results, including tables."""
        parts = []
        all_tables = []

        for tool_name, results in context_data.items():
            if isinstance(results, list):
                for r in results:
                    if isinstance(r, dict):
                        ticker = r.get("ticker", "")
                        year = r.get("year", "")
                        text = r.get("text", "")
                        parts.append(f"[{ticker} {year}] {text}")

                        # Extract tables from text
                        tables = extract_tables_from_text(text, ticker, year)
                        all_tables.extend(tables)
                    elif isinstance(r, str):
                        parts.append(r)

        # Add formatted tables
        if all_tables:
            table_context = format_table_for_context(all_tables[:3])
            if table_context:
                parts.append(f"\nStructured Data:\n{table_context}")

        return "\n\n---\n\n".join(parts[:10])

    def _generate_answer(self, query: str, context: str, model: str, conv_context: str = "") -> str:
        """Generate answer using LLM."""
        system_prompt = """You are a financial analyst AI specializing in SEC 10-K filings.

Rules:
1. Answer based ONLY on the provided context
2. Include specific numbers and dates
3. Reference company ticker and year when citing
4. If info not available, say "I don't have that information"
5. Be concise but thorough
6. For comparisons, use a table format"""

        # Add conversation context if available
        user_content = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
        if conv_context:
            user_content = f"Previous conversation:\n{conv_context}\n\n{user_content}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        resp = self.llm.chat(model=model, messages=messages)
        return _clean_response(resp.content)

    def _reflect(self, query: str, answer: str, context: str) -> dict:
        """Self-reflect on answer quality."""
        prompt = f"""Evaluate this answer to a financial query.

Query: {query}
Answer: {answer}

Is this answer:
1. Complete? Does it fully answer the question?
2. Accurate? Are the numbers correct based on the context?
3. Well-sourced? Does it cite specific companies/years?

Respond with JSON:
{{
    "needs_improvement": true/false,
    "issues": ["issue1", "issue2"],
    "missing_info": "what info is missing"
}}"""

        resp = self.llm.chat(
            model=settings.ollama_simple_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
        )

        try:
            json_match = re.search(r'\{.*\}', resp.content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {"needs_improvement": False, "issues": [], "missing_info": ""}

    def _retrieve_more(self, query: str, missing_info: str) -> str:
        """Retrieve additional context based on missing info."""
        enhanced_query = f"{query} {missing_info}"
        results = self.retriever.retrieve(enhanced_query, top_k=3)
        return _build_context(results)

    def _extract_citations(self, query: str, context_data: dict) -> list[str]:
        """Extract relevant citations."""
        query_lower = query.lower()
        mentioned = set()

        company_keywords = {
            "MSFT": ["microsoft", "msft"],
            "AMZN": ["amazon", "amzn"],
            "META": ["meta", "facebook"],
            "GOOG": ["google", "alphabet", "goog"],
            "TSLA": ["tesla", "tsla"],
        }

        for ticker, keywords in company_keywords.items():
            for kw in keywords:
                if kw in query_lower:
                    mentioned.add(ticker)
                    break

        citations = []
        seen = set()

        for tool_name, results in context_data.items():
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
