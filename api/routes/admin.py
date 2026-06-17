"""Admin endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.database.admin_auth import (
    authenticate_user,
    create_session,
    validate_session,
    logout_session,
    list_users,
    create_user,
    delete_user,
)
from src.database.cache import cache

logger = logging.getLogger(__name__)
router = APIRouter()


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
def admin_list_users():
    """List all users (admin only)."""
    return {"users": list_users()}


@router.post("/admin/users")
def admin_create_user(username: str, password: str, role: str = "user"):
    """Create a new user (admin only)."""
    result = create_user(username, password, role)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/admin/users/{username}")
def admin_delete_user(username: str):
    """Delete a user (admin only)."""
    if delete_user(username):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="User not found")


@router.get("/admin/validate")
def admin_validate(token: str):
    """Validate admin session."""
    user = validate_session(token)
    if user:
        return {"valid": True, "user": user}
    return {"valid": False}


@router.post("/admin/clear-cache")
def clear_cache():
    """Clear Redis cache."""
    try:
        cache.clear()
        return {"status": "cleared"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
