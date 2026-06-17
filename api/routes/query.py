"""Query endpoints (sync + streaming)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.models import QueryRequest, QueryResponse
from src.agents.graph import LangGraphOrchestrator
from src.agents.memory import memory
from src.agents.guardrails import guardrails
from src.generation.cost_tracker import CostTracker, QueryCostRecord
from src.ml.routing import CostAwareRouter
from src.ml.query_processor import QueryProcessor
from src.database.cache import cache
from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

orchestrator = LangGraphOrchestrator()
cost_tracker = CostTracker()

SYSTEM_PROMPT = """You are a financial analyst AI specializing in SEC 10-K filings.

Rules:
1. Answer based ONLY on the provided context
2. Include specific numbers and dates
3. Reference company ticker and year when citing
4. If info not available, say "I don't have that information"
5. Be concise but thorough
6. For comparisons, use a table format"""


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    query_text = req.query.strip()

    input_result = guardrails.validate_input(query_text)
    if not input_result.passed:
        raise HTTPException(status_code=400, detail=input_result.message)

    query_text = input_result.sanitized_input or query_text

    try:
        cached = cache.get_query_cache(query_text, settings.ollama_simple_model)
        if cached:
            return QueryResponse(**cached)
    except Exception as e:
        logger.warning(f"Cache check failed: {e}")

    try:
        response = orchestrator.run(query_text)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {e}") from e

    answer = response["answer"]
    output_result = guardrails.validate_output(
        answer=answer,
        context=response.get("context", ""),
        query=query_text,
    )
    if "add_disclaimer" in output_result.issues:
        answer = guardrails.output.add_disclaimer(answer)

    try:
        cost_tracker.record(QueryCostRecord(
            query=query_text,
            model=response["model_used"],
            complexity=response["complexity"],
            tokens_in=0,
            tokens_out=0,
            cost_usd=response["total_cost_usd"],
            latency_ms=response["total_latency_ms"],
        ))
    except Exception as e:
        logger.warning(f"Cost tracking failed: {e}")

    result = QueryResponse(
        answer=answer,
        complexity=response["complexity"],
        model_used=response["model_used"],
        cost_usd=response["total_cost_usd"],
        latency_ms=response["total_latency_ms"],
        citations=response["citations"],
        steps_count=len(response["steps"]),
    )

    try:
        cache.set_query_cache(query_text, response["model_used"], result.model_dump())
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

    return result


@router.post("/query/stream")
def query_stream(req: QueryRequest):
    """Stream response token by token for better UX."""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    def generate():
        try:
            from src.retrieval.hybrid import HybridRetriever
            from src.generation.llm_client import OllamaClient

            llm = OllamaClient()
            retriever = HybridRetriever()

            processor = QueryProcessor(llm_client=llm)
            processed = processor.process(
                req.query.strip(),
                enable_rewrite=True,
                enable_hyde=True,
                enable_multi_query=True,
            )
            all_queries = processor.get_all_queries(processed)

            router_obj = CostAwareRouter()
            routing_result = router_obj.route(processed.rewritten)
            complexity = routing_result.complexity
            model = routing_result.model

            all_results = []
            for q in all_queries:
                results = retriever.retrieve(q, top_k=5)
                all_results.extend(results)

            seen_texts = {}
            for r in all_results:
                key = r.text[:200]
                if key not in seen_texts or r.score > seen_texts[key].score:
                    seen_texts[key] = r
            unique_results = sorted(seen_texts.values(), key=lambda x: x.score, reverse=True)[:5]

            context = _build_context(unique_results, max_chars=2000)

            history = memory.get_history(limit=10)
            history_text = ""
            if history:
                history_parts = []
                for msg in history:
                    prefix = "User" if msg["role"] == "user" else "Assistant"
                    history_parts.append(f"{prefix}: {msg['content'][:200]}")
                history_text = "\n".join(history_parts)

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            if history_text:
                messages.append({"role": "user", "content": f"Previous conversation:\n{history_text}\n\n---"})
            messages.append({
                "role": "user",
                "content": f"Document Context:\n{context}\n\n---\n\nQuestion: {processed.rewritten}\n\nProvide a direct answer based on the context above:",
            })

            full_text = ""
            for chunk in llm.chat_stream(model=model, messages=messages):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            citations = []
            seen = set()
            for r in unique_results:
                if r.metadata:
                    ticker = r.metadata.get("ticker", "")
                    year = r.metadata.get("year", "")
                    key = f"{ticker}_{year}"
                    if ticker and key not in seen:
                        seen.add(key)
                        citations.append(f"{ticker} {year}")

            metadata = {
                "type": "metadata",
                "complexity": complexity,
                "model_used": model,
                "citations": citations,
                "cost_usd": routing_result.cost_estimate,
                "steps_count": 3,
                "query_processed": {
                    "original": processed.original,
                    "rewritten": processed.rewritten,
                    "hyde_used": processed.hyde_query is not None,
                    "expanded_count": len(processed.expanded_queries) if processed.expanded_queries else 0,
                },
            }
            yield f"data: {json.dumps(metadata)}\n\n"

            memory.add_message("user", req.query.strip())
            memory.add_message("assistant", full_text)
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _build_context(results: list, max_chars: int = 2000) -> str:
    """Build context string from retrieval results."""
    from src.agents.graph import _build_context_from_tools

    context_data = {}
    for r in results:
        ticker = r.metadata.get("ticker", "") if r.metadata else ""
        year = r.metadata.get("year", "") if r.metadata else ""
        if ticker not in context_data:
            context_data[ticker] = []
        context_data[ticker].append({"text": r.text[:500], "ticker": ticker, "year": year})

    return _build_context_from_tools(context_data)
