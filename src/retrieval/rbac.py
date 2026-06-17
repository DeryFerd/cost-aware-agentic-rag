"""Role-based access control for document retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.retrieval.hybrid import RetrievalResult


@dataclass
class RBACConfig:
    """Maps document tickers to allowed roles."""

    ticker_permissions: dict[str, set[str]] = field(default_factory=dict)

    def get_allowed_roles(self, ticker: str) -> set[str]:
        """Return roles allowed to see a given ticker. Empty set = everyone."""
        return self.ticker_permissions.get(ticker, set())

    def is_role_allowed(self, ticker: str, role: str) -> bool:
        """Check whether *role* may access *ticker*."""
        allowed = self.get_allowed_roles(ticker)
        # Empty set means unrestricted (visible to all authenticated users)
        if not allowed:
            return True
        return role in allowed


class DocumentAccessControl:
    """Filter retrieval results based on user role and ticker permissions."""

    def __init__(self, config: RBACConfig | None = None) -> None:
        self.config = config or RBACConfig()

    def filter_by_access(
        self,
        results: list[RetrievalResult],
        user_role: str,
        allowed_tickers: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Return only results the user is permitted to see.

        Parameters
        ----------
        results:
            Retrieval results to filter.
        user_role:
            ``"admin"`` bypasses all checks.
        allowed_tickers:
            Explicit whitelist. When *None* the default permissions from
            :class:`RBACConfig` are used.
        """
        if user_role == "admin":
            return results

        filtered: list[RetrievalResult] = []
        for r in results:
            ticker = (r.metadata or {}).get("ticker", "").upper()

            if allowed_tickers is not None:
                if ticker in {t.upper() for t in allowed_tickers}:
                    filtered.append(r)
            else:
                if self.config.is_role_allowed(ticker, user_role):
                    filtered.append(r)

        return filtered


_access_control: DocumentAccessControl | None = None


def get_access_control() -> DocumentAccessControl:
    """Return a module-level singleton :class:`DocumentAccessControl`."""
    global _access_control
    if _access_control is None:
        _access_control = DocumentAccessControl()
    return _access_control
