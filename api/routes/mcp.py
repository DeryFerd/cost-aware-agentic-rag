"""MCP (Model Context Protocol) server — exposes RAG tools as MCP-compatible endpoints.

MCP is the 2026 standard for LLM tool connectivity. This exposes:
- search SEC filings
- get financial data
- compare companies
- list available companies
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents.mcp_server import MCPToolRegistry

logger = logging.getLogger(__name__)
router = APIRouter()


class MCPToolRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the MCP tool to call")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class MCPToolResponse(BaseModel):
    tool_name: str
    result: Any
    status: str = "success"


@router.get("/mcp/tools")
async def list_mcp_tools():
    """List all available MCP tools with their schemas."""
    registry = MCPToolRegistry()
    return {
        "tools": registry.list_tools(),
        "count": len(registry.list_tools()),
    }


@router.post("/mcp/call")
async def call_mcp_tool(req: MCPToolRequest):
    """Call an MCP tool by name with arguments."""
    registry = MCPToolRegistry()

    tool_def = registry.get_tool(req.tool_name)
    if not tool_def:
        raise HTTPException(status_code=404, detail=f"Tool '{req.tool_name}' not found")

    try:
        result = registry.handle_request(req.tool_name, req.arguments)
        return MCPToolResponse(
            tool_name=req.tool_name,
            result=result,
            status="success",
        )
    except Exception as e:
        logger.error(f"MCP tool call failed: {e}")
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {e}") from e
