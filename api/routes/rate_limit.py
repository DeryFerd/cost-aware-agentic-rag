"""Rate limiter admin endpoints — view stats and configuration."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.database.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)
router = APIRouter()


class RateLimitConfigUpdate(BaseModel):
    requests_per_minute: int | None = Field(None, ge=1)
    requests_per_hour: int | None = Field(None, ge=1)
    burst_size: int | None = Field(None, ge=1)


@router.get("/rate-limits/stats")
async def rate_limit_stats(tenant_id: str | None = None):
    """Get rate limiting statistics."""
    stats = rate_limiter.get_stats(tenant_id=tenant_id)
    return stats


@router.post("/rate-limits/config")
async def update_rate_limit_config(req: RateLimitConfigUpdate):
    """Update rate limiter configuration."""
    updates = {}
    if req.requests_per_minute is not None:
        updates["requests_per_minute"] = req.requests_per_minute
    if req.requests_per_hour is not None:
        updates["requests_per_hour"] = req.requests_per_hour
    if req.burst_size is not None:
        updates["burst_size"] = req.burst_size

    if not updates:
        raise HTTPException(status_code=400, detail="No config updates provided")

    rate_limiter.configure(**updates)
    return {"status": "updated", "config": updates}
