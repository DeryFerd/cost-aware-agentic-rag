"""Register existing system prompts as version 1.0.0 in the prompt registry."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.generation.prompt_registry import PromptRegistry
from src.generation.prompts import (
    CITE_PROMPT,
    COMPARE_PROMPT,
    ROUTER_PROMPT,
    SUMMARIZE_PROMPT,
    SYSTEM_PROMPT,
    VALIDATE_PROMPT,
)

PROMPTS = [
    {
        "name": "system",
        "template": SYSTEM_PROMPT,
        "metadata": {
            "author": "system",
            "description": "Core system prompt for the financial analyst AI",
        },
    },
    {
        "name": "router",
        "template": ROUTER_PROMPT,
        "metadata": {
            "author": "system",
            "description": "Classifies query complexity as simple or complex",
        },
    },
    {
        "name": "summarize",
        "template": SUMMARIZE_PROMPT,
        "metadata": {
            "author": "system",
            "description": "Summarizes retrieved passages to answer a question",
        },
    },
    {
        "name": "compare",
        "template": COMPARE_PROMPT,
        "metadata": {
            "author": "system",
            "description": "Compares financial metrics across companies/years",
        },
    },
    {
        "name": "cite",
        "template": CITE_PROMPT,
        "metadata": {
            "author": "system",
            "description": "Extracts specific citations supporting a claim",
        },
    },
    {
        "name": "validate",
        "template": VALIDATE_PROMPT,
        "metadata": {
            "author": "system",
            "description": "Validates answer quality for completeness, accuracy, citations, clarity",
        },
    },
]


def main():
    registry = PromptRegistry()
    for p in PROMPTS:
        registry.register(
            name=p["name"],
            version="1.0.0",
            template=p["template"],
            metadata=p["metadata"],
        )
        print(f"Registered: {p['name']} v1.0.0")

    print(f"\n{len(PROMPTS)} prompts registered successfully.")


if __name__ == "__main__":
    main()
