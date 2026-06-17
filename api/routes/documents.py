"""Document and conversation endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from src.agents.memory import memory
from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/documents")
def list_documents():
    """List all indexed documents with metadata."""
    documents = []
    doc_id = 1

    if settings.raw_dir.exists():
        for company_dir in settings.raw_dir.iterdir():
            if company_dir.is_dir():
                ticker = company_dir.name
                for year_dir in company_dir.iterdir():
                    if year_dir.is_dir():
                        try:
                            year = int(year_dir.name)
                        except ValueError:
                            continue

                        files = list(year_dir.glob("*"))
                        txt_files = [f for f in files if f.suffix.lower() == ".txt"]
                        total_size = sum(f.stat().st_size for f in txt_files)

                        documents.append({
                            "id": doc_id,
                            "ticker": ticker,
                            "year": year,
                            "filing_type": "10-K",
                            "status": "indexed",
                            "chunks": max(10, total_size // 5000),
                            "size": f"{total_size // 1024} KB" if total_size > 1024 else f"{total_size} B",
                        })
                        doc_id += 1

    return {"documents": documents}


@router.get("/conversation/history")
def conversation_history():
    """Get conversation history."""
    return {"history": memory.get_history(limit=20)}


@router.delete("/conversation/clear")
def clear_conversation():
    """Clear conversation history."""
    memory.clear()
    return {"status": "cleared"}


@router.get("/conversation/context")
def conversation_context():
    """Get conversation context string for LLM."""
    context = memory.get_context_string()
    return {"context": context, "history": memory.get_history(limit=10)}


@router.post("/conversation/session")
def create_session(session_id: str):
    """Create or switch to a conversation session."""
    memory.current_session = session_id
    return {"status": "ok", "session_id": session_id}


@router.get("/conversation/sessions")
def list_sessions():
    """List all conversation sessions."""
    return {"sessions": memory.get_session_ids()}


@router.delete("/conversation/session/{session_id}")
def delete_session(session_id: str):
    """Delete a conversation session."""
    if session_id in memory.conversations:
        del memory.conversations[session_id]
    return {"status": "deleted"}
