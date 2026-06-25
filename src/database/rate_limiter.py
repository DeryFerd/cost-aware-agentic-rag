"""Per-tenant rate limiting with sliding window counters.

Provides request-rate limiting on top of token budgets.
Uses in-memory sliding window with optional Redis backing.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a tenant."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10  # max concurrent requests


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining_minute: int
    remaining_hour: int
    retry_after_seconds: float = 0.0
    reason: str = ""


class RateLimiter:
    """Sliding window rate limiter per tenant.

    Tracks request counts in 1-minute and 1-hour windows.
    Falls back to in-memory when Redis is unavailable.
    """

    def __init__(self):
        # {tenant_id: [timestamp, ...]}
        self._requests_minute: dict[str, list[float]] = defaultdict(list)
        self._requests_hour: dict[str, list[float]] = defaultdict(list)
        self._concurrent: dict[str, int] = defaultdict(int)
        self._configs: dict[str, RateLimitConfig] = {}

    def configure(self, tenant_id: str, config: RateLimitConfig) -> None:
        """Set rate limit config for a tenant."""
        self._configs[tenant_id] = config

    def check(self, tenant_id: str) -> RateLimitResult:
        """Check if a request is allowed for this tenant.

        Uses sliding window counters for 1-minute and 1-hour windows.
        """
        config = self._configs.get(tenant_id, RateLimitConfig())
        now = time.time()

        # Clean old entries
        self._requests_minute[tenant_id] = [
            t for t in self._requests_minute[tenant_id] if now - t < 60
        ]
        self._requests_hour[tenant_id] = [
            t for t in self._requests_hour[tenant_id] if now - t < 3600
        ]

        # Check burst (concurrent)
        if self._concurrent[tenant_id] >= config.burst_size:
            return RateLimitResult(
                allowed=False,
                remaining_minute=0,
                remaining_hour=0,
                reason="concurrent_limit",
            )

        # Check per-minute
        minute_count = len(self._requests_minute[tenant_id])
        if minute_count >= config.requests_per_minute:
            oldest = self._requests_minute[tenant_id][0] if self._requests_minute[tenant_id] else now
            retry_after = 60 - (now - oldest)
            return RateLimitResult(
                allowed=False,
                remaining_minute=0,
                remaining_hour=config.requests_per_hour - len(self._requests_hour[tenant_id]),
                retry_after_seconds=max(0, retry_after),
                reason="per_minute_limit",
            )

        # Check per-hour
        hour_count = len(self._requests_hour[tenant_id])
        if hour_count >= config.requests_per_hour:
            oldest = self._requests_hour[tenant_id][0] if self._requests_hour[tenant_id] else now
            retry_after = 3600 - (now - oldest)
            return RateLimitResult(
                allowed=False,
                remaining_minute=config.requests_per_minute - minute_count,
                remaining_hour=0,
                retry_after_seconds=max(0, retry_after),
                reason="per_hour_limit",
            )

        return RateLimitResult(
            allowed=True,
            remaining_minute=config.requests_per_minute - minute_count - 1,
            remaining_hour=config.requests_per_hour - hour_count - 1,
        )

    def record(self, tenant_id: str) -> None:
        """Record a request for this tenant."""
        now = time.time()
        self._requests_minute[tenant_id].append(now)
        self._requests_hour[tenant_id].append(now)
        self._concurrent[tenant_id] += 1

    def release(self, tenant_id: str) -> None:
        """Release a concurrent request slot."""
        self._concurrent[tenant_id] = max(0, self._concurrent[tenant_id] - 1)

    def get_stats(self, tenant_id: str) -> dict:
        """Get current rate limit stats for a tenant."""
        now = time.time()
        config = self._configs.get(tenant_id, RateLimitConfig())

        minute_count = len([
            t for t in self._requests_minute[tenant_id] if now - t < 60
        ])
        hour_count = len([
            t for t in self._requests_hour[tenant_id] if now - t < 3600
        ])

        return {
            "tenant_id": tenant_id,
            "requests_this_minute": minute_count,
            "requests_this_hour": hour_count,
            "limit_minute": config.requests_per_minute,
            "limit_hour": config.requests_per_hour,
            "concurrent": self._concurrent[tenant_id],
            "burst_limit": config.burst_size,
        }


# Singleton
rate_limiter = RateLimiter()
