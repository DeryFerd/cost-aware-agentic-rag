"""Human-in-the-loop escalation for uncertain answers.

When the agent is not confident in its answer, it can escalate
to a human reviewer instead of providing a potentially incorrect response.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EscalationTicket:
    """A ticket for human review."""
    ticket_id: str
    query: str
    answer: str
    confidence: float
    reason: str
    model_used: str
    complexity: str
    timestamp: str
    status: str = "pending"  # pending, reviewed, resolved
    reviewer_notes: str = ""
    final_answer: str = ""


class HumanEscalation:
    """Handle escalation of uncertain answers to human reviewers.

    Triggers escalation when:
    - Answer confidence is below threshold
    - Guardrails flag multiple issues
    - Reflector suggests the answer needs improvement
    - Query is high-stakes (financial advice, legal, etc.)
    """

    # High-stakes keywords that trigger escalation
    HIGH_STAKES_KEYWORDS = [
        "invest", "buy", "sell", "trade", "portfolio",
        "legal", "lawsuit", "regulatory", "compliance",
        "fraud", "bankruptcy", "default",
    ]

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        max_guardrail_issues: int = 3,
        output_dir: str | Path | None = None,
    ):
        self.confidence_threshold = confidence_threshold
        self.max_guardrail_issues = max_guardrail_issues
        self.output_dir = Path(output_dir) if output_dir else settings.data_dir / "escalations"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._ticket_counter = 0

    def should_escalate(
        self,
        query: str,
        answer: str,
        confidence: float = 0.0,
        guardrail_issues: list[str] | None = None,
        reflection_issues: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Determine if the answer should be escalated to a human.

        Returns:
            Tuple of (should_escalate, reason)
        """
        # Check confidence threshold
        if confidence < self.confidence_threshold:
            return True, f"low_confidence:{confidence:.2f}"

        # Check guardrail issues
        if guardrail_issues and len(guardrail_issues) > self.max_guardrail_issues:
            return True, f"too_many_guardrail_issues:{len(guardrail_issues)}"

        # Check reflection issues
        if reflection_issues and len(reflection_issues) >= 2:
            return True, f"reflection_flagged:{len(reflection_issues)}_issues"

        # Check high-stakes content
        query_lower = query.lower()
        for keyword in self.HIGH_STAKES_KEYWORDS:
            if keyword in query_lower:
                return True, f"high_stakes_keyword:{keyword}"

        # Check if answer contains hedging language (low confidence signal)
        hedging = ["i think", "i believe", "maybe", "possibly", "not sure"]
        hedging_count = sum(1 for h in hedging if h in answer.lower())
        if hedging_count >= 2:
            return True, f"hedging_language:{hedging_count}"

        return False, ""

    def create_ticket(
        self,
        query: str,
        answer: str,
        confidence: float,
        reason: str,
        model_used: str = "",
        complexity: str = "",
    ) -> EscalationTicket:
        """Create an escalation ticket for human review."""
        self._ticket_counter += 1
        ticket_id = f"ESC-{datetime.now(UTC).strftime('%Y%m%d')}-{self._ticket_counter:04d}"

        ticket = EscalationTicket(
            ticket_id=ticket_id,
            query=query,
            answer=answer,
            confidence=confidence,
            reason=reason,
            model_used=model_used,
            complexity=complexity,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Save ticket
        filepath = self.output_dir / f"{ticket_id}.json"
        with open(filepath, "w") as f:
            json.dump(asdict(ticket), f, indent=2)

        logger.info(f"Escalation ticket created: {ticket_id} (reason: {reason})")
        return ticket

    def get_pending_tickets(self) -> list[EscalationTicket]:
        """Get all pending escalation tickets."""
        tickets = []
        for filepath in sorted(self.output_dir.glob("ESC-*.json")):
            with open(filepath) as f:
                data = json.load(f)
                if data.get("status") == "pending":
                    tickets.append(EscalationTicket(**data))
        return tickets

    def resolve_ticket(
        self,
        ticket_id: str,
        final_answer: str,
        reviewer_notes: str = "",
    ) -> bool:
        """Resolve an escalation ticket with a human-reviewed answer."""
        filepath = self.output_dir / f"{ticket_id}.json"
        if not filepath.exists():
            return False

        with open(filepath) as f:
            data = json.load(f)

        data["status"] = "resolved"
        data["final_answer"] = final_answer
        data["reviewer_notes"] = reviewer_notes

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Escalation ticket resolved: {ticket_id}")
        return True


# Singleton
human_escalation = HumanEscalation()
