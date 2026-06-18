"""Redis caching layer."""

import json
from datetime import datetime
from typing import Any

import redis

from src.config import settings


class CacheManager:
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        value = self.redis.get(key)
        if value:
            return json.loads(value)
        return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL (default 1 hour)."""
        return self.redis.setex(key, ttl, json.dumps(value))

    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        return self.redis.delete(key) > 0

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return self.redis.exists(key) > 0

    def flush(self) -> bool:
        """Flush all cache."""
        return self.redis.flushdb()

    def get_query_cache(self, query: str, model: str) -> dict | None:
        """Get cached query result."""
        key = f"query:{model}:{hash(query)}"
        return self.get(key)

    def set_query_cache(self, query: str, model: str, result: dict, ttl: int = 1800):
        """Cache query result (default 30 minutes)."""
        key = f"query:{model}:{hash(query)}"
        self.set(key, result, ttl)

    def get_user_rate_limit(self, user_id: int) -> int:
        """Get current rate limit count for user."""
        key = f"rate:{user_id}"
        count = self.redis.get(key)
        return int(count) if count else 0

    def increment_rate_limit(self, user_id: int, window: int = 60) -> int:
        """Increment rate limit counter (default 1 minute window)."""
        key = f"rate:{user_id}"
        count = self.redis.incr(key)
        if count == 1:
            self.redis.expire(key, window)
        return count

    def get_cost_today(self, user_id: int) -> float:
        """Get total cost for user today."""
        key = f"cost:{user_id}:{datetime.now().strftime('%Y-%m-%d')}"
        cost = self.redis.get(key)
        return float(cost) if cost else 0.0

    def add_cost(self, user_id: int, cost: float) -> float:
        """Add cost to user's daily total."""
        key = f"cost:{user_id}:{datetime.now().strftime('%Y-%m-%d')}"
        new_cost = self.redis.incrbyfloat(key, cost)
        self.redis.expire(key, 86400)  # 24 hours
        return new_cost


# Singleton
cache = CacheManager()
