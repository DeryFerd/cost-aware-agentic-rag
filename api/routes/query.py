"""Query endpoints (sync + streaming)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from api.models import QueryRequest, QueryResponse
from src.agents.graph import LangGraphOrchestrator
from src.agents.guardrails import guardrails
from src.agents.human_escalation import human_escalation
from src.agents.memory import memory
from src.config import settings
from src.database.audit import audit
from src.database.cache import cache
from src.database.rate_limiter import rate_limiter
from src.database.tenants import get_tenant_manager
from src.eval.online_eval import online_evaluator
from src.generation.cost_tracker import CostTracker, QueryCostRecord
from src.generation.structured_output import QueryAnswer, StructuredOutputParser
from src.ml.query_processor import QueryProcessor
from src.ml.routing import CostAwareRouter
from src.retrieval.tenant_filter import get_tenant_filter

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
async def query(
    request: Request,
    req: QueryRequest,
    x_tenant_id: Annotated[str | None, Header()] = None,
    tenant_id: Annotated[str | None, Query()] = None,
) -> QueryResponse:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Resolve tenant: header takes precedence, then query param
    resolved_tenant_id = x_tenant_id or tenant_id
    tenant_manager = get_tenant_manager()
    tenant = None
    if resolved_tenant_id:
        tenant = tenant_manager.get_tenant(resolved_tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        if not tenant.get("is_active", True):
            raise HTTPException(status_code=403, detail="Tenant account is disabled")

        budget = tenant_manager.check_token_budget(resolved_tenant_id)
        if not budget["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily token limit reached. Used {budget['used']}/{budget['limit']} tokens today.",
            )

        # Rate limiting per tenant (sliding window)
        rate_check = rate_limiter.check(resolved_tenant_id)
        if not rate_check.allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({rate_check.reason}). Retry after {rate_check.retry_after_seconds:.0f}s.",
                headers={"Retry-After": str(int(rate_check.retry_after_seconds))},
            )
        rate_limiter.record(resolved_tenant_id)

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
        response = await asyncio.to_thread(
            orchestrator.run, query_text, "default", resolved_tenant_id or ""
        )
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

    tokens_used = response.get("tokens_in", 0) + response.get("tokens_out", 0)

    try:
        cost_tracker.record(QueryCostRecord(
            query=query_text,
            model=response["model_used"],
            complexity=response["complexity"],
            tokens_in=response.get("tokens_in", 0),
            tokens_out=response.get("tokens_out", 0),
            cost_usd=response["total_cost_usd"],
            latency_ms=response["total_latency_ms"],
        ))
    except Exception as e:
        logger.warning(f"Cost tracking failed: {e}")

    # Record usage per tenant
    if resolved_tenant_id:
        try:
            tenant_manager.record_usage(
                resolved_tenant_id,
                tokens=tokens_used,
                cost=response["total_cost_usd"],
            )
        except Exception as e:
            logger.warning(f"Usage recording failed: {e}")

    result = QueryResponse(
        answer=answer,
        complexity=response["complexity"],
        model_used=response["model_used"],
        cost_usd=response["total_cost_usd"],
        latency_ms=response["total_latency_ms"],
        citations=response["citations"],
        steps_count=len(response["steps"]),
        trace_id=getattr(request.state, "trace_id", None),
    )

    audit.log_event(
        actor=resolved_tenant_id or "anonymous",
        action="query",
        target=query_text[:200],
        outcome="success",
        details={
            "model": response["model_used"],
            "complexity": response["complexity"],
            "cost_usd": response["total_cost_usd"],
        },
    )

    # Online evaluation — sample 5% of production queries for quality tracking
    try:
        if online_evaluator.should_sample():
            online_evaluator.sample_and_evaluate(
                query=query_text,
                answer=answer,
                model_used=response["model_used"],
                complexity=response["complexity"],
                latency_ms=response["total_latency_ms"],
                cost_usd=response["total_cost_usd"],
            )
    except Exception as e:
        logger.warning(f"Online eval sampling failed: {e}")

    # Human escalation — check if answer needs human review
    try:
        should_escalate, escalation_reason = human_escalation.should_escalate(
            query=query_text,
            answer=answer,
            confidence=0.7,  # Default confidence
        )
        if should_escalate:
            ticket = human_escalation.create_ticket(
                query=query_text,
                answer=answer,
                confidence=0.7,
                reason=escalation_reason,
                model_used=response["model_used"],
                complexity=response["complexity"],
            )
            result.escalation_ticket_id = ticket.ticket_id
    except Exception as e:
        logger.warning(f"Human escalation check failed: {e}")

    try:
        cache.set_query_cache(query_text, response["model_used"], result.model_dump())
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

    return result


@router.post("/query/stream")
def query_stream(
    req: QueryRequest,
    x_tenant_id: Annotated[str | None, Header()] = None,
    tenant_id: Annotated[str | None, Query()] = None,
):
    """Stream response token by token for better UX."""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Resolve tenant
    resolved_tenant_id = x_tenant_id or tenant_id
    tenant_manager = get_tenant_manager()
    tenant = None
    if resolved_tenant_id:
        tenant = tenant_manager.get_tenant(resolved_tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        if not tenant.get("is_active", True):
            raise HTTPException(status_code=403, detail="Tenant account is disabled")

        budget = tenant_manager.check_token_budget(resolved_tenant_id)
        if not budget["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily token limit reached. Used {budget['used']}/{budget['limit']} tokens today.",
            )

        # Rate limiting per tenant (sliding window)
        rate_check = rate_limiter.check(resolved_tenant_id)
        if not rate_check.allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({rate_check.reason}). Retry after {rate_check.retry_after_seconds:.0f}s.",
                headers={"Retry-After": str(int(rate_check.retry_after_seconds))},
            )
        rate_limiter.record(resolved_tenant_id)

    def generate():
        try:
            from src.generation.llm_client import OllamaClient
            from src.retrieval.hybrid import HybridRetriever

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

            # Apply tenant filtering
            if resolved_tenant_id:
                tenant_filter = get_tenant_filter()
                unique_results = tenant_filter.filter_results(
                    unique_results, resolved_tenant_id
                )

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

            # Record usage per tenant
            if resolved_tenant_id:
                try:
                    tenant_manager.record_usage(
                        resolved_tenant_id,
                        tokens=len(full_text),  # rough estimate
                        cost=routing_result.cost_estimate,
                    )
                except Exception as e:
                    logger.warning(f"Usage recording failed: {e}")

            memory.add_message("user", req.query.strip())
            memory.add_message("assistant", full_text)
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/query/structured")
async def query_structured(
    req: QueryRequest,
    x_tenant_id: Annotated[str | None, Header()] = None,
    tenant_id: Annotated[str | None, Query()] = None,
):
    """Query endpoint that returns structured output parsed into a schema."""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    resolved_tenant_id = x_tenant_id or tenant_id
    tenant_manager = get_tenant_manager()
    if resolved_tenant_id:
        tenant = tenant_manager.get_tenant(resolved_tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        if not tenant.get("is_active", True):
            raise HTTPException(status_code=403, detail="Tenant account is disabled")

        budget = tenant_manager.check_token_budget(resolved_tenant_id)
        if not budget["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily token limit reached. Used {budget['used']}/{budget['limit']} tokens today.",
            )

        # Rate limiting per tenant (sliding window)
        rate_check = rate_limiter.check(resolved_tenant_id)
        if not rate_check.allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({rate_check.reason}). Retry after {rate_check.retry_after_seconds:.0f}s.",
                headers={"Retry-After": str(int(rate_check.retry_after_seconds))},
            )
        rate_limiter.record(resolved_tenant_id)

    query_text = req.query.strip()
    input_result = guardrails.validate_input(query_text)
    if not input_result.passed:
        raise HTTPException(status_code=400, detail=input_result.message)
    query_text = input_result.sanitized_input or query_text

    try:
        response = await asyncio.to_thread(
            orchestrator.run, query_text, "default", resolved_tenant_id or ""
        )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {e}") from e

    raw_output = response["answer"]
    parser = StructuredOutputParser()
    is_valid, parsed = parser.validate(raw_output, QueryAnswer)

    if not is_valid:
        parsed = parser.repair(raw_output, QueryAnswer)

    if not parsed.get("answer"):
        parsed["answer"] = raw_output

    return {
        "structured": parsed,
        "raw": raw_output,
        "is_valid": is_valid,
        "complexity": response["complexity"],
        "model_used": response["model_used"],
        "cost_usd": response["total_cost_usd"],
        "latency_ms": response["total_latency_ms"],
        "citations": response["citations"],
    }


@router.post("/query/multi-agent", response_model=QueryResponse)
async def query_multi_agent(
    request: Request,
    req: QueryRequest,
    x_tenant_id: Annotated[str | None, Header()] = None,
    tenant_id: Annotated[str | None, Query()] = None,
) -> QueryResponse:
    """Multi-agent pipeline: Research → Analysis → Verification."""
    from src.agents.multi_agent import MultiAgentOrchestrator

    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    resolved_tenant_id = x_tenant_id or tenant_id
    tenant_manager = get_tenant_manager()
    tenant = None
    if resolved_tenant_id:
        tenant = tenant_manager.get_tenant(resolved_tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        if not tenant.get("is_active", True):
            raise HTTPException(status_code=403, detail="Tenant account is disabled")

        budget = tenant_manager.check_token_budget(resolved_tenant_id)
        if not budget["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily token limit reached. Used {budget['used']}/{budget['limit']} tokens today.",
            )

        rate_check = rate_limiter.check(resolved_tenant_id)
        if not rate_check.allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({rate_check.reason}). Retry after {rate_check.retry_after_seconds:.0f}s.",
                headers={"Retry-After": str(int(rate_check.retry_after_seconds))},
            )
        rate_limiter.record(resolved_tenant_id)

    query_text = req.query.strip()
    input_result = guardrails.validate_input(query_text)
    if not input_result.passed:
        raise HTTPException(status_code=400, detail=input_result.message)
    query_text = input_result.sanitized_input or query_text

    multi_orchestrator = MultiAgentOrchestrator()

    try:
        response = await asyncio.to_thread(
            multi_orchestrator.run, query_text, "default", resolved_tenant_id or ""
        )
    except Exception as e:
        logger.error(f"Multi-agent query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {e}") from e

    answer = response["answer"]
    tokens_used = response.get("tokens_in", 0) + response.get("tokens_out", 0)

    try:
        cost_tracker.record_query(QueryCostRecord(
            query=query_text,
            model=response["model_used"],
            complexity=response["complexity"],
            tokens_in=response.get("tokens_in", 0),
            tokens_out=response.get("tokens_out", 0),
            cost_usd=response["total_cost_usd"],
            latency_ms=response["total_latency_ms"],
            tenant_id=resolved_tenant_id or "",
        ))
    except Exception as e:
        logger.warning(f"Cost tracking failed: {e}")

    if resolved_tenant_id:
        try:
            tenant_manager.record_usage(
                resolved_tenant_id,
                tokens=tokens_used,
                cost=response["total_cost_usd"],
            )
        except Exception as e:
            logger.warning(f"Usage recording failed: {e}")

    result = QueryResponse(
        answer=answer,
        complexity=response["complexity"],
        model_used=response["model_used"],
        cost_usd=response["total_cost_usd"],
        latency_ms=response["total_latency_ms"],
        citations=response["citations"],
        steps_count=len(response["steps"]),
        trace_id=getattr(request.state, "trace_id", None),
        agent_type="multi_agent",
    )

    # Online eval
    try:
        if online_evaluator.should_sample():
            online_evaluator.sample_and_evaluate(
                query=query_text,
                answer=answer,
                model_used=response["model_used"],
                complexity=response["complexity"],
                latency_ms=response["total_latency_ms"],
                cost_usd=response["total_cost_usd"],
            )
    except Exception as e:
        logger.warning(f"Online eval sampling failed: {e}")

    # Human escalation
    try:
        should_escalate, escalation_reason = human_escalation.should_escalate(
            query=query_text,
            answer=answer,
            confidence=0.7,
        )
        if should_escalate:
            ticket = human_escalation.create_ticket(
                query=query_text,
                answer=answer,
                confidence=0.7,
                reason=escalation_reason,
                model_used=response["model_used"],
                complexity=response["complexity"],
            )
            result.escalation_ticket_id = ticket.ticket_id
    except Exception as e:
        logger.warning(f"Human escalation check failed: {e}")

    audit.log_event(
        actor=resolved_tenant_id or "anonymous",
        action="query_multi_agent",
        target=query_text[:200],
        outcome="success",
        details={
            "model": response["model_used"],
            "complexity": response["complexity"],
            "cost_usd": response["total_cost_usd"],
            "agent_type": "multi_agent",
        },
    )

    memory.add_message("user", req.query.strip())
    memory.add_message("assistant", answer)

    return result


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
