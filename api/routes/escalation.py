"""Human escalation endpoints — manage escalation tickets for human review.

Tickets are created automatically when:
- Query confidence is low (< 0.5)
- High-stakes query (regulatory, M&A, fraud)
- Hedging language detected
- Conflicting information
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from src.agents.human_escalation import EscalationStatus, human_escalation

logger = logging.getLogger(__name__)
router = APIRouter()


class EscalationTicketResponse(BaseModel):
    ticket_id: str
    query: str
    answer: str
    confidence: float
    reason: str
    status: str
    model_used: str
    complexity: str


class ResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=1, max_length=5000)


@router.get("/escalations")
async def list_escalations(
    status: str | None = None,
    x_tenant_id: Annotated[str | None, Header()] = None,
):
    """List escalation tickets, optionally filtered by status."""
    status_filter = None
    if status:
        try:
            status_filter = EscalationStatus(status)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from ve

    tickets = human_escalation.get_pending_tickets(
        status=status_filter,
        tenant_id=x_tenant_id,
    )
    return {
        "tickets": [t.__dict__ for t in tickets],
        "count": len(tickets),
    }


@router.get("/escalations/{ticket_id}")
async def get_escalation(ticket_id: str):
    """Get a specific escalation ticket."""
    ticket = human_escalation.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket.__dict__


@router.post("/escalations/{ticket_id}/resolve")
async def resolve_escalation(
    ticket_id: str,
    req: ResolveRequest,
    x_tenant_id: Annotated[str | None, Header()] = None,
):
    """Resolve an escalation ticket with human-provided resolution."""
    ticket = human_escalation.resolve_ticket(
        ticket_id=ticket_id,
        resolution_notes=req.resolution_notes,
        reviewer=x_tenant_id or "anonymous",
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"status": "resolved", "ticket": ticket.__dict__}


@router.get("/escalations/stats")
async def escalation_stats():
    """Get escalation statistics."""
    stats = human_escalation.get_stats()
    return stats
