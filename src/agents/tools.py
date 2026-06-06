"""Agent tools for Agentic RAG."""

from __future__ import annotations

from typing import Any

from src.retrieval.hybrid import HybridRetriever
from src.generation.llm_client import OllamaClient


class ToolRegistry:
    """Registry of tools available to the agent."""

    def __init__(self, retriever: HybridRetriever, llm: OllamaClient) -> None:
        self.retriever = retriever
        self.llm = llm
        self.tools: dict[str, dict[str, Any]] = {
            "retrieve": {
                "function": self._retrieve,
                "description": (
                    "Search the SEC 10-K knowledge base for relevant document chunks. "
                    "Input: query string. Returns ranked passages with scores."
                ),
            },
            "summarize": {
                "function": self._summarize,
                "description": (
                    "Summarize retrieved passages into a concise answer. "
                    "Input: list of passages and original query."
                ),
            },
            "compare": {
                "function": self._compare,
                "description": (
                    "Compare financial metrics across multiple companies or years. "
                    "Input: companies list and metric to compare."
                ),
            },
            "cite": {
                "function": self._cite,
                "description": (
                    "Extract specific citations with page numbers from passages. "
                    "Input: passages and the claim to cite."
                ),
            },
        }

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI-style tool schemas for Ollama."""
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "input": {
                                "type": "string",
                                "description": "The input for this tool",
                            }
                        },
                        "required": ["input"],
                    },
                },
            }
            for name, info in self.tools.items()
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool and return its result as a string."""
        if tool_name not in self.tools:
            return f"Error: Unknown tool '{tool_name}'"

        try:
            result = self.tools[tool_name]["function"](**arguments)
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"

    def _retrieve(self, input: str) -> list[dict]:
        """Search the knowledge base."""
        results = self.retriever.retrieve(input, top_k=5)
        return [
            {
                "text": r.text[:500],
                "score": round(r.score, 4),
                "source": r.metadata.get("source", "unknown") if r.metadata else "unknown",
            }
            for r in results
        ]

    def _summarize(self, input: str) -> str:
        """Summarize passages using LLM."""
        from src.config import settings

        resp = self.llm.chat(
            model=settings.ollama_simple_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a financial analyst. Summarize the following passages "
                        "into a clear, concise answer. Include key numbers and facts."
                    ),
                },
                {"role": "user", "content": input},
            ],
            temperature=0.1,
        )
        return resp.content

    def _compare(self, input: str) -> str:
        """Compare metrics across companies."""
        from src.config import settings

        resp = self.llm.chat(
            model=settings.ollama_complex_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a financial analyst. Compare the following metrics "
                        "across companies. Present in a structured table format."
                    ),
                },
                {"role": "user", "content": input},
            ],
            temperature=0.1,
        )
        return resp.content

    def _cite(self, input: str) -> str:
        """Extract citations from passages."""
        from src.config import settings

        resp = self.llm.chat(
            model=settings.ollama_simple_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract specific citations from the text. "
                        "Format: [Source: document, Page: X] — exact quote"
                    ),
                },
                {"role": "user", "content": input},
            ],
            temperature=0.0,
        )
        return resp.content
