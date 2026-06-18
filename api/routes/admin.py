"""Admin endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.database.admin_auth import (
    authenticate_user,
    create_session,
    create_user,
    delete_user,
    list_users,
    logout_session,
    require_admin,
    validate_session,
)
from src.database.audit import audit
from src.database.cache import cache
from src.database.tenants import get_tenant_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Tenant Models ──────────────────────────────────────────────────
class CreateTenantRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=4)
    allowed_tickers: list[str] = Field(default_factory=list)
    daily_token_limit: int = Field(default=100_000, ge=1_000)


class UpdateTenantRequest(BaseModel):
    allowed_tickers: list[str] | None = None
    daily_token_limit: int | None = None
    is_active: bool | None = None
    password: str | None = None


@router.post("/admin/login")
def admin_login(username: str, password: str):
    """Admin login."""
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_session(user["username"])
    return {"token": token, "user": user}


@router.post("/admin/logout")
def admin_logout(token: str):
    """Admin logout."""
    if logout_session(token):
        return {"status": "logged_out"}
    raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/admin/users")
def admin_list_users(
    _user: Annotated[dict, Depends(require_admin)],
):
    """List all users (admin only)."""
    return {"users": list_users()}


@router.post("/admin/users")
def admin_create_user(
    username: str,
    password: str,
    role: str = "user",
    _user: Annotated[dict, Depends(require_admin)] = None,
):
    """Create a new user (admin only)."""
    result = create_user(username, password, role)
    if "error" in result:
        audit.log_event(
            actor=_user.get("username", "unknown"),
            action="create_user",
            target=username,
            outcome="failure",
            details={"error": result["error"]},
        )
        raise HTTPException(status_code=400, detail=result["error"])
    audit.log_event(
        actor=_user.get("username", "unknown"),
        action="create_user",
        target=username,
        outcome="success",
        details={"role": role},
    )
    return result


@router.delete("/admin/users/{username}")
def admin_delete_user(
    username: str,
    _user: Annotated[dict, Depends(require_admin)] = None,
):
    """Delete a user (admin only)."""
    if delete_user(username):
        audit.log_event(
            actor=_user.get("username", "unknown"),
            action="delete_user",
            target=username,
            outcome="success",
        )
        return {"status": "deleted"}
    audit.log_event(
        actor=_user.get("username", "unknown"),
        action="delete_user",
        target=username,
        outcome="failure",
        details={"error": "User not found"},
    )
    raise HTTPException(status_code=404, detail="User not found")


@router.get("/admin/validate")
def admin_validate(token: str):
    """Validate admin session."""
    user = validate_session(token)
    if user:
        return {"valid": True, "user": user}
    return {"valid": False}


@router.post("/admin/clear-cache")
def clear_cache(
    _user: Annotated[dict, Depends(require_admin)] = None,
):
    """Clear Redis cache."""
    try:
        cache.clear()
        audit.log_event(
            actor=_user.get("username", "unknown"),
            action="clear_cache",
            target="redis",
            outcome="success",
        )
        return {"status": "cleared"}
    except Exception as e:
        audit.log_event(
            actor=_user.get("username", "unknown"),
            action="clear_cache",
            target="redis",
            outcome="failure",
            details={"error": str(e)},
        )
        return {"status": "error", "message": str(e)}


# ── Tenant Management ──────────────────────────────────────────────
@router.post("/tenants")
def create_tenant(
    req: CreateTenantRequest,
    _user: Annotated[dict, Depends(require_admin)] = None,
):
    """Create a new tenant."""
    try:
        mgr = get_tenant_manager()
        tenant = mgr.create_tenant(
            username=req.username,
            password=req.password,
            allowed_tickers=req.allowed_tickers,
            daily_token_limit=req.daily_token_limit,
        )
        audit.log_event(
            actor=_user.get("username", "unknown"),
            action="create_tenant",
            target=req.username,
            outcome="success",
            details={"allowed_tickers": req.allowed_tickers},
        )
        return {"tenant": tenant}
    except ValueError as e:
        audit.log_event(
            actor=_user.get("username", "unknown"),
            action="create_tenant",
            target=req.username,
            outcome="failure",
            details={"error": str(e)},
        )
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/tenants")
def list_tenants(
    _user: Annotated[dict, Depends(require_admin)] = None,
):
    """List all tenants."""
    mgr = get_tenant_manager()
    return {"tenants": mgr.list_tenants()}


@router.get("/tenants/{tenant_id}")
def get_tenant(
    tenant_id: str,
    _user: Annotated[dict, Depends(require_admin)] = None,
):
    """Get tenant by ID."""
    mgr = get_tenant_manager()
    tenant = mgr.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"tenant": tenant}


@router.put("/tenants/{tenant_id}")
def update_tenant(
    tenant_id: str,
    req: UpdateTenantRequest,
    _user: Annotated[dict, Depends(require_admin)] = None,
):
    """Update a tenant."""
    try:
        mgr = get_tenant_manager()
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        tenant = mgr.update_tenant(tenant_id, updates)
        audit.log_event(
            actor=_user.get("username", "unknown"),
            action="update_tenant",
            target=tenant_id,
            outcome="success",
            details={"fields_updated": list(updates.keys())},
        )
        return {"tenant": tenant}
    except ValueError as e:
        audit.log_event(
            actor=_user.get("username", "unknown"),
            action="update_tenant",
            target=tenant_id,
            outcome="failure",
            details={"error": str(e)},
        )
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/tenants/{tenant_id}")
def delete_tenant(
    tenant_id: str,
    _user: Annotated[dict, Depends(require_admin)] = None,
):
    """Delete a tenant."""
    mgr = get_tenant_manager()
    if mgr.delete_tenant(tenant_id):
        audit.log_event(
            actor=_user.get("username", "unknown"),
            action="delete_tenant",
            target=tenant_id,
            outcome="success",
        )
        return {"status": "deleted"}
    audit.log_event(
        actor=_user.get("username", "unknown"),
        action="delete_tenant",
        target=tenant_id,
        outcome="failure",
        details={"error": "Tenant not found"},
    )
    raise HTTPException(status_code=404, detail="Tenant not found")


@router.get("/tenants/{tenant_id}/usage")
def get_tenant_usage(
    tenant_id: str,
    days: int = Query(default=7, ge=1, le=90),
    _user: Annotated[dict, Depends(require_admin)] = None,
):
    """Get tenant usage statistics."""
    try:
        mgr = get_tenant_manager()
        stats = mgr.get_usage_stats(tenant_id, days=days)
        budget = mgr.check_token_budget(tenant_id)
        return {"usage": stats, "budget": budget}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
