"""Admin authentication (file-based, bcrypt hashing, no auto-create)."""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import Header, HTTPException, status

from src.config import settings

logger = logging.getLogger(__name__)

ADMIN_DIR = settings.data_dir / "admin"
ADMIN_DIR.mkdir(parents=True, exist_ok=True)

USERS_FILE = ADMIN_DIR / "users.json"
SESSIONS_FILE = ADMIN_DIR / "sessions.json"


def _hash_password(password: str) -> str:
    """Hash password with bcrypt (salted)."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        import hashlib
        import secrets as _secrets
        salt = _secrets.token_hex(16)
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() + f":{salt}"


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash (bcrypt or salted sha256)."""
    try:
        import bcrypt
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ImportError:
        if ":" in password_hash:
            stored_hash, salt = password_hash.rsplit(":", 1)
            import hashlib
            return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == stored_hash
        return False


def _load_users() -> dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_users(users: dict) -> None:
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _load_sessions() -> dict:
    if SESSIONS_FILE.exists():
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_sessions(sessions: dict) -> None:
    SESSIONS_FILE.write_text(json.dumps(sessions, indent=2), encoding="utf-8")


def init_admin(username: str | None = None, password: str | None = None) -> None:
    """Create admin user. Requires explicit credentials (no defaults).

    Args:
        username: Admin username. If None, uses ADMIN_USERNAME env var.
        password: Admin password. If None, uses ADMIN_PASSWORD env var.
    """
    import os
    username = username or os.environ.get("ADMIN_USERNAME")
    password = password or os.environ.get("ADMIN_PASSWORD")

    if not username or not password:
        logger.info("No admin credentials provided. Skipping admin creation.")
        return

    users = _load_users()
    if username not in users:
        users[username] = {
            "username": username,
            "password_hash": _hash_password(password),
            "role": "admin",
            "created_at": datetime.now().isoformat(),
            "is_active": True,
        }
        _save_users(users)
        logger.info(f"Admin user '{username}' created.")


def authenticate_user(username: str, password: str) -> dict | None:
    """Authenticate user credentials."""
    from src.database.audit import audit

    users = _load_users()
    user = users.get(username)
    if not user:
        audit.log_event(actor=username, action="auth", target=username, outcome="failure", details={"reason": "user_not_found"})
        return None
    if not _verify_password(password, user["password_hash"]):
        audit.log_event(actor=username, action="auth", target=username, outcome="failure", details={"reason": "invalid_password"})
        return None
    if not user.get("is_active", True):
        audit.log_event(actor=username, action="auth", target=username, outcome="failure", details={"reason": "account_disabled"})
        return None
    audit.log_event(actor=username, action="auth", target=username, outcome="success")
    return {"username": user["username"], "role": user["role"]}


def create_session(username: str) -> str:
    """Create a session token for authenticated user."""
    token = secrets.token_hex(32)
    sessions = _load_sessions()
    sessions[token] = {
        "username": username,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
    }
    _save_sessions(sessions)
    return token


def validate_session(token: str) -> dict | None:
    """Validate session token and return user info."""
    sessions = _load_sessions()
    session = sessions.get(token)
    if not session:
        return None
    if datetime.fromisoformat(session["expires_at"]) < datetime.now():
        del sessions[token]
        _save_sessions(sessions)
        return None
    return {"username": session["username"], "role": "admin"}


def logout_session(token: str) -> bool:
    """Logout (delete) a session."""
    sessions = _load_sessions()
    if token in sessions:
        del sessions[token]
        _save_sessions(sessions)
        return True
    return False


def list_users() -> list[dict]:
    """List all users."""
    users = _load_users()
    return [
        {
            "username": u["username"],
            "role": u["role"],
            "created_at": u["created_at"],
            "is_active": u.get("is_active", True),
        }
        for u in users.values()
    ]


def create_user(username: str, password: str, role: str = "user") -> dict:
    """Create a new user."""
    users = _load_users()
    if username in users:
        return {"error": "User already exists"}
    users[username] = {
        "username": username,
        "password_hash": _hash_password(password),
        "role": role,
        "created_at": datetime.now().isoformat(),
        "is_active": True,
    }
    _save_users(users)
    return {"username": username, "role": role}


def delete_user(username: str) -> bool:
    """Delete a user."""
    users = _load_users()
    if username in users:
        del users[username]
        _save_users(users)
        return True
    return False


# ── FastAPI Dependency ────────────────────────────────────────────────
def require_admin(authorization: str | None = Header(None)) -> dict:
    """FastAPI dependency that enforces admin auth on protected routes.

    Expects ``Authorization: Bearer <token>`` header.
    Returns the validated user dict on success.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.removeprefix("Bearer ").strip()
    user = validate_session(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    return user
