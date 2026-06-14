"""Ollama Cloud LLM client with cost tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ollama import Client

from src.config import settings


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


# Approximate costs per 1M tokens (USD) — simulated for demonstration
# Real Ollama Cloud pricing may vary; these show the cost-aware routing works
MODEL_COSTS: dict[str, dict[str, float]] = {
    "gemma3:4b": {"input": 0.05, "output": 0.10},   # lightweight model
    "gemma3:27b": {"input": 0.25, "output": 0.50},   # heavy model
}


class OllamaClient:
    """Thin wrapper around Ollama Cloud with cost estimation."""

    def __init__(
        self,
        host: str = settings.ollama_host,
        api_key: str = settings.ollama_api_key,
    ) -> None:
        self.client = Client(
            host=host,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        t0 = time.perf_counter()

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if tools:
            kwargs["tools"] = tools

        resp = self.client.chat(**kwargs)
        latency = (time.perf_counter() - t0) * 1000

        msg = resp.get("message", {})
        content = msg.get("content", "")
        usage = resp.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        cost = self._estimate_cost(model, tokens_in, tokens_out)

        return LLMResponse(
            content=content,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency,
            cost_usd=cost,
            raw=resp,
        )

    def classify_complexity(self, query: str) -> str:
        """Quick heuristic + LLM classification for routing.

        .. deprecated::
            Use ``CostAwareRouter.route()`` from ``src.ml.routing`` instead.
            This method is kept as a fallback for ``CostAwareRouter._llm_classify``
            when the trained classifier confidence is low.
        """
        # Rule-based fast path
        q = query.lower()
        simple_keywords = ["what is", "define", "when did", "who is", "list", "show me"]
        complex_keywords = ["compare", "analyze", "explain why", "implications", "risk", "forecast"]

        if any(kw in q for kw in complex_keywords):
            return "complex"
        if any(kw in q for kw in simple_keywords):
            return "simple"

        # LLM tie-breaker for ambiguous queries
        resp = self.chat(
            model=settings.ollama_simple_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify the following financial query as 'simple' (factual lookup, "
                        "single fact retrieval) or 'complex' (requires comparison, analysis, "
                        "reasoning across multiple sections). Reply with one word only."
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=10,
        )
        return resp.content.strip().lower()

    def select_model(self, complexity: str) -> str:
        if complexity == "complex":
            return settings.ollama_complex_model
        return settings.ollama_simple_model

    def chat_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ):
        """Stream chat response token by token."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": True,
        }

        for chunk in self.client.chat(**kwargs):
            if chunk.get("message", {}).get("content"):
                yield chunk["message"]["content"]

    def chat_with_image(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Chat with image input for vision models.

        Messages format for images:
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this image?"},
                {"type": "image", "image": "base64_encoded_image"}
            ]
        }
        """
        t0 = time.perf_counter()

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

        resp = self.client.chat(**kwargs)
        latency = (time.perf_counter() - t0) * 1000

        msg = resp.get("message", {})
        content = msg.get("content", "")
        usage = resp.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        cost = self._estimate_cost(model, tokens_in, tokens_out)

        return LLMResponse(
            content=content,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency,
            cost_usd=cost,
            raw=resp,
        )

    @staticmethod
    def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
        costs = MODEL_COSTS.get(model, {"input": 0.0, "output": 0.0})
        return (tokens_in * costs["input"] + tokens_out * costs["output"]) / 1_000_000
