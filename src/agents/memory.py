"""Conversation memory for multi-turn interactions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


class ConversationMemory:
    """Store and manage conversation history."""

    def __init__(self, max_history: int = 10) -> None:
        self.max_history = max_history
        self.conversations: dict[str, list[Message]] = {}
        self.current_session: str = "default"

    def add_message(
        self,
        role: str,
        content: str,
        session_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Add a message to conversation history."""
        session = session_id or self.current_session

        if session not in self.conversations:
            self.conversations[session] = []

        msg = Message(
            role=role,
            content=content,
            metadata=metadata or {},
        )

        self.conversations[session].append(msg)

        # Trim to max history
        if len(self.conversations[session]) > self.max_history:
            self.conversations[session] = self.conversations[session][-self.max_history:]

    def get_history(self, session_id: str | None = None, limit: int = 5) -> list[dict]:
        """Get recent conversation history."""
        session = session_id or self.current_session
        history = self.conversations.get(session, [])

        return [
            {"role": msg.role, "content": msg.content}
            for msg in history[-limit:]
        ]

    def get_context_string(self, session_id: str | None = None) -> str:
        """Get conversation history as context string for LLM."""
        history = self.get_history(session_id, limit=5)

        if not history:
            return ""

        parts = []
        for msg in history:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{prefix}: {msg['content'][:200]}")

        return "\n".join(parts)

    def clear(self, session_id: str | None = None) -> None:
        """Clear conversation history."""
        session = session_id or self.current_session
        self.conversations[session] = []

    def get_session_ids(self) -> list[str]:
        """Get all session IDs."""
        return list(self.conversations.keys())


# Global memory instance
memory = ConversationMemory()
