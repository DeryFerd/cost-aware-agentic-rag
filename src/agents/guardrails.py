"""Input/output guardrails for the RAG system.

Provides:
1. Input validation (query length, content filtering)
2. Output grounding checks (hallucination detection)
3. PII detection and redaction
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    """Result of guardrail check."""
    passed: bool
    message: str
    sanitized_input: Optional[str] = None
    issues: list[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class InputGuardrails:
    """Validate and sanitize user input."""

    MAX_QUERY_LENGTH = 2000
    MIN_QUERY_LENGTH = 3

    # PII patterns
    PII_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    }

    # Blocked patterns (prompt injection attempts)
    BLOCKED_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"you\s+are\s+now\s+a",
        r"system\s*:\s*",
        r"assistant\s*:\s*",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"\[INST\]",
        r"\[/INST\]",
    ]

    def validate(self, query: str) -> GuardrailResult:
        """Validate input query."""
        issues = []
        sanitized = query.strip()

        # Check length
        if len(sanitized) < self.MIN_QUERY_LENGTH:
            return GuardrailResult(
                passed=False,
                message=f"Query too short (minimum {self.MIN_QUERY_LENGTH} characters)",
                issues=["query_too_short"],
            )

        if len(sanitized) > self.MAX_QUERY_LENGTH:
            sanitized = sanitized[:self.MAX_QUERY_LENGTH]
            issues.append("query_truncated")

        # Check for prompt injection
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                return GuardrailResult(
                    passed=False,
                    message="Query contains blocked content",
                    issues=["prompt_injection_detected"],
                )

        # Detect and redact PII
        for pii_type, pattern in self.PII_PATTERNS.items():
            if re.search(pattern, sanitized, re.IGNORECASE):
                sanitized = re.sub(pattern, f"[REDACTED_{pii_type.upper()}]", sanitized)
                issues.append(f"pii_{pii_type}_redacted")

        passed = len(issues) == 0 or all("truncated" in i or "redacted" in i for i in issues)

        return GuardrailResult(
            passed=passed,
            message="Input validated" if passed else f"Found {len(issues)} issues",
            sanitized_input=sanitized,
            issues=issues,
        )


class OutputGuardrails:
    """Validate output quality and grounding."""

    # Financial disclaimer keywords
    DISCLAIMER_KEYWORDS = [
        "guarantee",
        "guaranteed",
        "certain",
        "definitely",
        "will happen",
        "predict",
        "forecast with certainty",
    ]

    # Hallucination indicators
    HALLUCINATION_INDICATORS = [
        "i think",
        "i believe",
        "probably",
        "might be",
        "could be",
        "according to my knowledge",
        "i recall",
    ]

    def validate(
        self,
        answer: str,
        context: str,
        query: str,
    ) -> GuardrailResult:
        """Validate output quality."""
        issues = []
        answer_lower = answer.lower()

        # Check for financial advice language
        for keyword in self.DISCLAIMER_KEYWORDS:
            if keyword in answer_lower:
                issues.append(f"financial_advice_language: {keyword}")

        # Check if answer is grounded in context
        context_lower = context.lower()
        answer_words = set(answer_lower.split())
        context_words = set(context_lower.split())

        if answer_words:
            grounding_ratio = len(answer_words & context_words) / len(answer_words)
            if grounding_ratio < 0.3:
                issues.append(f"low_grounding: {grounding_ratio:.2f}")

        # Check for hallucination indicators
        for indicator in self.HALLUCINATION_INDICATORS:
            if indicator in answer_lower:
                issues.append(f"hallucination_indicator: {indicator}")

        # Check if answer addresses the query
        query_words = set(query.lower().split())
        if query_words:
            relevance = len(query_words & answer_words) / len(query_words)
            if relevance < 0.2:
                issues.append(f"low_relevance: {relevance:.2f}")

        # Add disclaimer if needed
        if issues:
            if not any("disclaimer" in i for i in issues):
                issues.append("add_disclaimer")

        passed = len(issues) == 0
        message = "Output validated" if passed else f"Found {len(issues)} issues"

        return GuardrailResult(
            passed=passed,
            message=message,
            issues=issues,
        )

    def add_disclaimer(self, answer: str) -> str:
        """Add financial disclaimer to answer."""
        disclaimer = "\n\n*Note: This information is from SEC filings and should not be considered financial advice.*"
        if disclaimer not in answer:
            return answer + disclaimer
        return answer


# ── Public API ────────────────────────────────────────────────────

class Guardrails:
    """Combined input/output guardrails."""

    def __init__(self):
        self.input = InputGuardrails()
        self.output = OutputGuardrails()

    def validate_input(self, query: str) -> GuardrailResult:
        """Validate input query."""
        return self.input.validate(query)

    def validate_output(
        self,
        answer: str,
        context: str,
        query: str,
    ) -> GuardrailResult:
        """Validate output quality."""
        return self.output.validate(answer, context, query)

    def process(
        self,
        query: str,
        answer: str,
        context: str,
    ) -> tuple[str, GuardrailResult]:
        """Process input and output through guardrails."""
        # Validate input
        input_result = self.input.validate(query)
        if not input_result.passed:
            return "I'm sorry, I cannot process that query.", input_result

        # Use sanitized input
        sanitized_query = input_result.sanitized_input or query

        # Validate output
        output_result = self.output.validate(answer, context, sanitized_query)

        # Add disclaimer if needed
        if "add_disclaimer" in output_result.issues:
            answer = self.output.add_disclaimer(answer)

        return answer, output_result


# Singleton instance
guardrails = Guardrails()
