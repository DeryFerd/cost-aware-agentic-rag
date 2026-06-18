"""Tenant-aware filtering for retrieval results."""

from __future__ import annotations

from src.database.tenants import get_tenant_manager
from src.retrieval.hybrid import RetrievalResult
from src.retrieval.rbac import DocumentAccessControl


class TenantFilter:
    """Filter retrieval results based on tenant's allowed tickers.

    Integrates with the existing RBAC system while adding tenant-level
    isolation on top.
    """

    def __init__(self, access_control: DocumentAccessControl | None = None) -> None:
        self._access_control = access_control or DocumentAccessControl()
        self._tenant_manager = get_tenant_manager()

    def filter_results(
        self,
        results: list[RetrievalResult],
        tenant_id: str,
    ) -> list[RetrievalResult]:
        """Filter retrieval results by tenant's allowed tickers.

        Args:
            results: Raw retrieval results.
            tenant_id: Tenant to filter for.

        Returns:
            Filtered results the tenant is permitted to see.
        """
        tenant = self._tenant_manager.get_tenant(tenant_id)
        if not tenant:
            return []

        allowed_tickers = {t.upper() for t in tenant["allowed_tickers"]}
        user_role = tenant.get("role", "tenant")

        if user_role == "admin":
            return results

        filtered: list[RetrievalResult] = []
        for r in results:
            ticker = (r.metadata or {}).get("ticker", "").upper()
            if not ticker:
                continue
            if ticker in allowed_tickers:
                filtered.append(r)

        return filtered

    def filter_results_with_rbac(
        self,
        results: list[RetrievalResult],
        tenant_id: str,
    ) -> list[RetrievalResult]:
        """Filter using both tenant allowed_tickers and RBAC config.

        This applies tenant filtering first, then RBAC on the remainder.
        """
        tenant = self._tenant_manager.get_tenant(tenant_id)
        if not tenant:
            return []

        allowed_tickers = tenant["allowed_tickers"]
        user_role = tenant.get("role", "tenant")

        return self._access_control.filter_by_access(
            results,
            user_role=user_role,
            allowed_tickers=allowed_tickers,
        )


def get_tenant_filter() -> TenantFilter:
    """Return a module-level singleton TenantFilter."""
    if not hasattr(get_tenant_filter, "_instance"):
        get_tenant_filter._instance = TenantFilter()
    return get_tenant_filter._instance
