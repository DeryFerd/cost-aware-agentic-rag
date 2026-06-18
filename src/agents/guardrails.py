"""Input/output guardrails for the RAG system.

Provides:
1. Input validation (query length, content filtering)
2. Output grounding checks (hallucination detection)
3. PII detection and redaction (regex + SpaCy NER when available)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try SpaCy for NER-based PII detection
_SPACY_AVAILABLE = False
_spacy_nlp = None
try:
    import spacy
    _spacy_nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    _SPACY_AVAILABLE = True
    logger.info("SpaCy NER available for PII detection")
except (ImportError, OSError):
    logger.info("SpaCy not available, using regex-only PII detection")


@dataclass
class GuardrailResult:
    """Result of guardrail check."""
    passed: bool
    message: str
    sanitized_input: str | None = None
    issues: list[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class InputGuardrails:
    """Validate and sanitize user input."""

    MAX_QUERY_LENGTH = 2000
    MIN_QUERY_LENGTH = 3

    # PII patterns (regex fallback)
    PII_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    }

    # SpaCy NER labels that map to PII types
    SPACY_PII_LABELS = {
        "PERSON": "name",
        "ORG": "organization",
        "GPE": "location",
        "LOC": "location",
        "MONEY": "financial",
        "DATE": "date",
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

        # Detect and redact PII (regex patterns)
        for pii_type, pattern in self.PII_PATTERNS.items():
            if re.search(pattern, sanitized, re.IGNORECASE):
                sanitized = re.sub(pattern, f"[REDACTED_{pii_type.upper()}]", sanitized)
                issues.append(f"pii_{pii_type}_redacted")

        # NER-based PII detection (SpaCy)
        if _SPACY_AVAILABLE and _spacy_nlp is not None:
            sanitized, ner_issues = self._ner_redact(sanitized)
            issues.extend(ner_issues)

        passed = len(issues) == 0 or all("truncated" in i or "redacted" in i for i in issues)

        return GuardrailResult(
            passed=passed,
            message="Input validated" if passed else f"Found {len(issues)} issues",
            sanitized_input=sanitized,
            issues=issues,
        )

    def _ner_redact(self, text: str) -> tuple[str, list[str]]:
        """Use SpaCy NER to detect and redact PII entities."""
        issues = []
        doc = _spacy_nlp(text)
        redacted = text

        # Process entities in reverse order to preserve offsets
        for ent in reversed(doc.ents):
            if ent.label_ in self.SPACY_PII_LABELS:
                pii_type = self.SPACY_PII_LABELS[ent.label_]
                # Only redact short entities (likely PII, not company names in financial context)
                if len(ent.text) < 40 and pii_type in ("name", "location", "financial"):
                    replacement = f"[REDACTED_{pii_type.upper()}]"
                    redacted = redacted[:ent.start_char] + replacement + redacted[ent.end_char:]
                    issues.append(f"ner_{ent.label_.lower()}_redacted")

        return redacted, issues


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

    # Regex for dollar amounts
    DOLLAR_AMOUNT_PATTERN = r'\$[\d,.]+\s*(?:billion|million|B|M)?'

    # Regex for nouns (words starting with capital or after common determiners)
    NOUN_PATTERN = r'\b[A-Za-z]{4,}\b'

    # Common stop words to filter out when computing key nouns
    STOP_WORDS = frozenset({
        "the", "and", "for", "that", "this", "with", "from", "are", "was",
        "were", "been", "have", "has", "had", "not", "but", "will", "can",
        "may", "its", "their", "they", "them", "than", "also", "which",
        "would", "could", "should", "about", "into", "each", "more", "other",
        "very", "such", "when", "what", "there", "based", "using", "used",
    })

    def _extract_dollar_amounts(self, text: str) -> list[str]:
        """Extract dollar amounts from text."""
        return re.findall(self.DOLLAR_AMOUNT_PATTERN, text, re.IGNORECASE)

    def _extract_key_nouns(self, text: str) -> set[str]:
        """Extract key nouns (words >= 4 chars, not stop words) from text."""
        words = re.findall(self.NOUN_PATTERN, text.lower())
        return {w for w in words if w not in self.STOP_WORDS and len(w) >= 4}

    def _check_cross_reference_amounts(self, answer: str, context: str) -> list[str]:
        """Check if dollar amounts in answer appear in context.

        Flags amounts in the answer that are NOT found in the context,
        which may indicate hallucinated figures.
        """
        issues = []
        answer_amounts = self._extract_dollar_amounts(answer)
        context_lower = context.lower()

        for amount in answer_amounts:
            amount_clean = amount.strip()
            if amount_clean.lower() not in context_lower:
                issues.append(f"ungrounded_amount: {amount_clean}")

        return issues

    def _check_semantic_grounding(self, answer: str, context: str) -> list[str]:
        """Check if answer shares enough key nouns with context.

        Uses simple word overlap. If answer shares < 20% of key nouns
        with context, flags as low grounding.
        """
        issues = []
        answer_nouns = self._extract_key_nouns(answer)
        context_nouns = self._extract_key_nouns(context)

        if not answer_nouns:
            return issues

        overlap = answer_nouns & context_nouns
        grounding_ratio = len(overlap) / len(answer_nouns) if answer_nouns else 0.0

        if grounding_ratio < 0.20:
            issues.append(f"low_semantic_grounding: {grounding_ratio:.2f}")

        return issues

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

        # Check if answer is grounded in context (existing word overlap)
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

        # Cross-reference: flag ungrounded dollar amounts
        issues.extend(self._check_cross_reference_amounts(answer, context))

        # Semantic grounding: key noun overlap check
        issues.extend(self._check_semantic_grounding(answer, context))

        # Add disclaimer if needed
        if issues and not any("disclaimer" in i for i in issues):
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
