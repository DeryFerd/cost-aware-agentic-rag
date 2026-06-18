"""Tenant management with file-based storage and per-tenant cost tracking."""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from src.config import settings

logger = logging.getLogger(__name__)

TENANTS_DIR = settings.data_dir / "tenants"
TENANTS_DIR.mkdir(parents=True, exist_ok=True)
TENANTS_FILE = TENANTS_DIR / "tenants.json"
USAGE_FILE = TENANTS_DIR / "usage.jsonl"


def _hash_password(password: str) -> str:
    """Hash password with bcrypt or fallback to sha256."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        import hashlib
        salt = secrets.token_hex(16)
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() + f":{salt}"


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    try:
        import bcrypt
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ImportError:
        if ":" in password_hash:
            stored_hash, salt = password_hash.rsplit(":", 1)
            import hashlib
            return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == stored_hash
        return False


class TenantManager:
    """File-based tenant management with per-tenant cost tracking."""

    def __init__(self) -> None:
        self._tenants_path = TENANTS_FILE
        self._usage_path = USAGE_FILE
        self._load()

    def _load(self) -> None:
        """Load tenants from file."""
        if self._tenants_path.exists():
            self._tenants: dict[str, dict] = json.loads(
                self._tenants_path.read_text(encoding="utf-8")
            )
        else:
            self._tenants = {}

    def _save(self) -> None:
        """Persist tenants to file."""
        self._tenants_path.write_text(
            json.dumps(self._tenants, indent=2, default=str), encoding="utf-8"
        )

    def _load_usage(self) -> list[dict]:
        """Load usage records from file."""
        if not self._usage_path.exists():
            return []
        records = []
        with open(self._usage_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def _save_usage_record(self, record: dict) -> None:
        """Append a usage record to file."""
        self._usage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._usage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def create_tenant(
        self,
        username: str,
        password: str,
        allowed_tickers: list[str],
        daily_token_limit: int = 100_000,
    ) -> dict:
        """Create a new tenant.

        Args:
            username: Unique username.
            password: Plain text password (will be hashed).
            allowed_tickers: List of stock tickers tenant can access.
            daily_token_limit: Max tokens allowed per day.

        Returns:
            Created tenant dict with id.

        Raises:
            ValueError: If username already exists.
        """
        if username in self._tenants:
            raise ValueError(f"Tenant '{username}' already exists")

        tenant_id = str(uuid.uuid4())
        tenant = {
            "id": tenant_id,
            "username": username,
            "password_hash": _hash_password(password),
            "role": "tenant",
            "allowed_tickers": [t.upper() for t in allowed_tickers],
            "daily_token_limit": daily_token_limit,
            "is_active": True,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._tenants[username] = tenant
        self._save()

        logger.info(f"Created tenant '{username}' (id={tenant_id})")
        return _sanitize_tenant(tenant)

    def get_tenant(self, tenant_id: str) -> dict | None:
        """Get tenant by ID."""
        for t in self._tenants.values():
            if t["id"] == tenant_id:
                return _sanitize_tenant(t)
        return None

    def _get_tenant_by_username(self, username: str) -> dict | None:
        """Get tenant by username."""
        t = self._tenants.get(username)
        return _sanitize_tenant(t) if t else None

    def list_tenants(self) -> list[dict]:
        """List all tenants (without password hashes)."""
        return [_sanitize_tenant(t) for t in self._tenants.values()]

    def update_tenant(self, tenant_id: str, updates: dict) -> dict:
        """Update a tenant's properties.

        Args:
            tenant_id: The tenant ID.
            updates: Dict of fields to update (allowed_tickers, daily_token_limit, is_active, password).

        Returns:
            Updated tenant dict.

        Raises:
            ValueError: If tenant not found.
        """
        tenant = self._find_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")

        if "allowed_tickers" in updates:
            tenant["allowed_tickers"] = [t.upper() for t in updates["allowed_tickers"]]
        if "daily_token_limit" in updates:
            tenant["daily_token_limit"] = updates["daily_token_limit"]
        if "is_active" in updates:
            tenant["is_active"] = updates["is_active"]
        if "password" in updates:
            tenant["password_hash"] = _hash_password(updates["password"])

        self._save()
        logger.info(f"Updated tenant {tenant_id}")
        return _sanitize_tenant(tenant)

    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant by ID.

        Returns:
            True if deleted, False if not found.
        """
        for username, t in self._tenants.items():
            if t["id"] == tenant_id:
                del self._tenants[username]
                self._save()
                logger.info(f"Deleted tenant '{username}' (id={tenant_id})")
                return True
        return False

    def authenticate(self, username: str, password: str) -> dict | None:
        """Authenticate a tenant by username and password.

        Returns:
            Sanitized tenant dict if authenticated, None otherwise.
        """
        tenant = self._tenants.get(username)
        if not tenant:
            return None
        if not tenant.get("is_active", True):
            return None
        if not _verify_password(password, tenant["password_hash"]):
            return None
        return _sanitize_tenant(tenant)

    def check_token_budget(self, tenant_id: str) -> dict:
        """Check if tenant has remaining token budget for today.

        Returns:
            Dict with allowed, used, remaining, limit fields.
        """
        tenant = self._find_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        usage = self._load_usage()

        used = sum(
            r["tokens"]
            for r in usage
            if r["tenant_id"] == tenant_id and r["date"] == today
        )

        limit = tenant["daily_token_limit"]
        remaining = max(0, limit - used)

        return {
            "allowed": remaining > 0,
            "used": used,
            "remaining": remaining,
            "limit": limit,
            "date": today,
        }

    def record_usage(self, tenant_id: str, tokens: int, cost: float) -> None:
        """Record token usage for a tenant.

        Args:
            tenant_id: The tenant ID.
            tokens: Number of tokens consumed.
            cost: USD cost of the query.
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        record = {
            "tenant_id": tenant_id,
            "tokens": tokens,
            "cost": cost,
            "date": today,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._save_usage_record(record)
        logger.debug(f"Recorded usage for tenant {tenant_id}: {tokens} tokens, ${cost:.6f}")

    def get_usage_stats(self, tenant_id: str, days: int = 7) -> dict:
        """Get usage statistics for a tenant over the last N days.

        Returns:
            Dict with daily breakdown and totals.
        """
        tenant = self._find_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")

        cutoff = datetime.now(UTC) - timedelta(days=days)
        usage = self._load_usage()

        relevant = [
            r for r in usage
            if r["tenant_id"] == tenant_id
            and datetime.fromisoformat(r["timestamp"]) > cutoff
        ]

        daily: dict[str, dict] = {}
        total_tokens = 0
        total_cost = 0.0
        query_count = 0

        for r in relevant:
            date = r["date"]
            if date not in daily:
                daily[date] = {"tokens": 0, "cost": 0.0, "queries": 0}
            daily[date]["tokens"] += r["tokens"]
            daily[date]["cost"] += r["cost"]
            daily[date]["queries"] += 1
            total_tokens += r["tokens"]
            total_cost += r["cost"]
            query_count += 1

        return {
            "tenant_id": tenant_id,
            "period_days": days,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
            "query_count": query_count,
            "daily": daily,
            "daily_limit": tenant["daily_token_limit"],
        }

    def _find_tenant_by_id(self, tenant_id: str) -> dict | None:
        """Find a raw tenant dict by ID."""
        for t in self._tenants.values():
            if t["id"] == tenant_id:
                return t
        return None


def _sanitize_tenant(tenant: dict) -> dict:
    """Remove password hash from tenant dict for safe output."""
    return {k: v for k, v in tenant.items() if k != "password_hash"}


# Module-level singleton
_tenant_manager: TenantManager | None = None


def get_tenant_manager() -> TenantManager:
    """Return a module-level singleton TenantManager."""
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager
