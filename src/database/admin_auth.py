"""Simplified admin authentication (file-based, no DB dependency)."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta

from src.config import settings

ADMIN_DIR = settings.data_dir / "admin"
ADMIN_DIR.mkdir(parents=True, exist_ok=True)

USERS_FILE = ADMIN_DIR / "users.json"
SESSIONS_FILE = ADMIN_DIR / "sessions.json"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


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


def init_admin() -> None:
    """Create default admin user if no users exist."""
    users = _load_users()
    if not users:
        users["admin"] = {
            "username": "admin",
            "password_hash": _hash_password("admin123"),
            "role": "admin",
            "created_at": datetime.now().isoformat(),
            "is_active": True,
        }
        _save_users(users)


def authenticate_user(username: str, password: str) -> dict | None:
    """Authenticate user credentials."""
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    if user["password_hash"] != _hash_password(password):
        return None
    if not user.get("is_active", True):
        return None
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


# Initialize on import
init_admin()
