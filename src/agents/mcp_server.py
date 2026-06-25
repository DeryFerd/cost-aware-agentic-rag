"""MCP (Model Context Protocol) server for SEC 10-K financial tools.

Exposes financial analysis tools as MCP-compatible endpoints.
This is the 2026 standard for agent tool connectivity.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.graph import _execute_compare, _execute_get_financials, _execute_search

logger = logging.getLogger(__name__)


# MCP-compatible tool definitions
MCP_TOOLS = [
    {
        "name": "search_sec_filings",
        "description": "Search SEC 10-K documents for information about a company or topic. Returns relevant text chunks with company ticker, year, and relevance score.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'Microsoft revenue 2024', 'Tesla risk factors')",
                },
                "ticker": {
                    "type": "string",
                    "description": "Company ticker symbol (optional): MSFT, AMZN, META, GOOG, TSLA, AAPL, NVDA",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_financial_metrics",
        "description": "Get specific financial metrics for a company from their SEC 10-K filing. Returns revenue, employee count, risk factors, or business description.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Company ticker: MSFT, AMZN, META, GOOG, TSLA, AAPL, NVDA",
                },
                "metric": {
                    "type": "string",
                    "description": "Metric to retrieve: revenue, employees, risks, description",
                },
                "year": {
                    "type": "string",
                    "description": "Filing year (optional, defaults to most recent)",
                },
            },
            "required": ["ticker", "metric"],
        },
    },
    {
        "name": "compare_companies",
        "description": "Compare financial metrics between multiple companies. Useful for competitive analysis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "string",
                    "description": "Comma-separated company tickers (e.g., 'MSFT,AMZN,GOOG')",
                },
                "metric": {
                    "type": "string",
                    "description": "Metric to compare: revenue, employees, risks",
                },
            },
            "required": ["tickers", "metric"],
        },
    },
    {
        "name": "list_available_companies",
        "description": "List all companies with SEC 10-K filings available in the system.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def handle_mcp_tool_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle an MCP tool call.

    Args:
        tool_name: Name of the tool to call
        arguments: Tool arguments

    Returns:
        MCP-compatible response with content and isError flag
    """
    try:
        if tool_name == "search_sec_filings":
            result_json = _execute_search(
                query=arguments.get("query", ""),
                ticker=arguments.get("ticker", ""),
            )
            results = json.loads(result_json)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(results, indent=2),
                    }
                ],
                "isError": False,
            }

        elif tool_name == "get_financial_metrics":
            result_json = _execute_get_financials(
                ticker=arguments.get("ticker", ""),
                metric=arguments.get("metric", ""),
                year=arguments.get("year", ""),
            )
            results = json.loads(result_json)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(results, indent=2),
                    }
                ],
                "isError": False,
            }

        elif tool_name == "compare_companies":
            result_json = _execute_compare(
                tickers=arguments.get("tickers", ""),
                metric=arguments.get("metric", ""),
            )
            results = json.loads(result_json)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(results, indent=2),
                    }
                ],
                "isError": False,
            }

        elif tool_name == "list_available_companies":
            companies = [
                {"ticker": "MSFT", "name": "Microsoft Corporation"},
                {"ticker": "AMZN", "name": "Amazon.com Inc"},
                {"ticker": "META", "name": "Meta Platforms Inc"},
                {"ticker": "GOOG", "name": "Alphabet Inc"},
                {"ticker": "TSLA", "name": "Tesla Inc"},
                {"ticker": "AAPL", "name": "Apple Inc"},
                {"ticker": "NVDA", "name": "NVIDIA Corporation"},
            ]
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(companies, indent=2),
                    }
                ],
                "isError": False,
            }

        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Unknown tool: {tool_name}",
                    }
                ],
                "isError": True,
            }

    except Exception as e:
        logger.error(f"MCP tool call failed: {tool_name} - {e}")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error executing {tool_name}: {str(e)}",
                }
            ],
            "isError": True,
        }


def get_mcp_tools() -> list[dict]:
    """Return MCP tool definitions."""
    return MCP_TOOLS


def get_mcp_server_info() -> dict:
    """Return MCP server info."""
    return {
        "name": "cost-aware-agentic-rag",
        "version": "0.1.0",
        "description": "SEC 10-K Financial Analysis RAG with cost-aware routing",
        "tools": MCP_TOOLS,
    }
