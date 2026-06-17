"""Structured output parsing and validation for LLM responses."""

from __future__ import annotations

import json
import re
from typing import TypeVar, Type

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class QueryAnswer(BaseModel):
    """Structured answer with citations and confidence."""

    answer: str
    citations: list[str] = []
    confidence: float = 0.0
    reasoning: str = ""


class ComparisonResult(BaseModel):
    """Structured comparison output."""

    entity_a: str
    entity_b: str
    metrics: dict = {}
    winner: str = ""
    summary: str = ""


class StructuredOutputParser:
    """Parse and validate LLM output into structured Pydantic models."""

    def parse_raw(self, model_output: str, schema: Type[T]) -> dict:
        """Parse LLM output into structured format.

        Tries JSON extraction first, then regex patterns.
        """
        # Attempt 1: Direct JSON parse
        result = self._try_json(model_output)
        if result is not None:
            return result

        # Attempt 2: Extract JSON from markdown code fences
        result = self._try_extract_from_fences(model_output)
        if result is not None:
            return result

        # Attempt 3: Extract JSON object from mixed text
        result = self._try_extract_json_object(model_output)
        if result is not None:
            return result

        # Attempt 4: Regex field extraction
        result = self._try_regex_extraction(model_output, schema)
        if result is not None:
            return result

        return {}

    def validate(self, model_output: str, schema: Type[T]) -> tuple[bool, dict]:
        """Validate output matches schema. Returns (is_valid, parsed_data)."""
        parsed = self.parse_raw(model_output, schema)
        if not parsed:
            return False, {}

        try:
            schema.model_validate(parsed)
            return True, parsed
        except Exception:
            return False, parsed

    def repair(self, model_output: str, schema: Type[T]) -> dict:
        """Repair malformed output and attempt parsing."""
        repaired = model_output

        # Strip markdown code fences
        repaired = re.sub(r"```(?:json)?\s*\n?", "", repaired)
        repaired = re.sub(r"```\s*$", "", repaired, flags=re.MULTILINE)

        # Fix trailing commas
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

        # Fix single quotes to double quotes
        repaired = repaired.replace("'", '"')

        # Try parsing the repaired string
        result = self._try_json(repaired)
        if result is not None:
            return result

        # Try extracting from the repaired string
        result = self._try_extract_json_object(repaired)
        if result is not None:
            return result

        # Last resort: build a minimal dict from available fields
        return self._build_minimal(model_output, schema)

    def _try_json(self, text: str) -> dict | None:
        """Try direct JSON parse."""
        try:
            data = json.loads(text.strip())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _try_extract_from_fences(self, text: str) -> dict | None:
        """Extract JSON from markdown code fences."""
        pattern = r"```(?:json)?\s*\n(.*?)\n\s*```"
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            result = self._try_json(match)
            if result is not None:
                return result
        return None

    def _try_extract_json_object(self, text: str) -> dict | None:
        """Extract the first JSON object from mixed text."""
        # Find the first { and match to closing }
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    result = self._try_json(candidate)
                    if result is not None:
                        return result
        return None

    def _try_regex_extraction(self, text: str, schema: Type[T]) -> dict | None:
        """Extract fields using regex patterns."""
        result: dict = {}

        # Common field patterns
        patterns = {
            "answer": r'"answer"\s*:\s*"([^"]*)"',
            "citations": r'"citations"\s*:\s*\[(.*?)\]',
            "confidence": r'"confidence"\s*:\s*([\d.]+)',
            "reasoning": r'"reasoning"\s*:\s*"([^"]*)"',
            "entity_a": r'"entity_a"\s*:\s*"([^"]*)"',
            "entity_b": r'"entity_b"\s*:\s*"([^"]*)"',
            "winner": r'"winner"\s*:\s*"([^"]*)"',
            "summary": r'"summary"\s*:\s*"([^"]*)"',
        }

        for field_name in schema.model_fields:
            if field_name in patterns:
                match = re.search(patterns[field_name], text)
                if match:
                    value = match.group(1)
                    if field_name == "confidence":
                        try:
                            result[field_name] = float(value)
                        except ValueError:
                            continue
                    elif field_name == "citations":
                        # Parse citation list
                        citations = re.findall(r'"([^"]*)"', value)
                        result[field_name] = citations
                    else:
                        result[field_name] = value

        return result if result else None

    def _build_minimal(self, text: str, schema: Type[T]) -> dict:
        """Build a minimal valid dict from available text."""
        result: dict = {}

        for field_name, field_info in schema.model_fields.items():
            default = field_info.default
            if default is not None and default != "":
                result[field_name] = default
            elif field_info.annotation == str:
                result[field_name] = ""
            elif field_info.annotation == float:
                result[field_name] = 0.0
            elif field_info.annotation == list:
                result[field_name] = []

        # At minimum, set answer to the raw text
        if "answer" in result:
            result["answer"] = text[:2000]

        return result
