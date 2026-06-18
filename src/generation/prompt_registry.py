"""Versioned prompt registry with storage, comparison, and rollback."""

from __future__ import annotations

import difflib
import json
import logging
from datetime import datetime
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)


class PromptRegistry:
    """Stores versioned prompts as JSON files in data/prompts/."""

    def __init__(self, storage_dir: str | Path | None = None):
        self.storage_dir = Path(storage_dir) if storage_dir else settings.data_dir / "prompts"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _prompt_path(self, name: str) -> Path:
        return self.storage_dir / f"{name}.json"

    def _load_prompt(self, name: str) -> dict:
        path = self._prompt_path(name)
        if not path.exists():
            return {"name": name, "versions": [], "current_version": None}
        with open(path) as f:
            return json.load(f)

    def _save_prompt(self, data: dict) -> None:
        path = self._prompt_path(data["name"])
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def register(
        self,
        name: str,
        version: str,
        template: str,
        metadata: dict | None = None,
    ) -> None:
        """Register a new version of a prompt."""
        data = self._load_prompt(name)

        for v in data["versions"]:
            if v["version"] == version:
                v["template"] = template
                v["metadata"] = metadata or {}
                v["updated_at"] = datetime.utcnow().isoformat()
                self._save_prompt(data)
                logger.info(f"Updated prompt '{name}' version {version}")
                return

        entry = {
            "version": version,
            "template": template,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        data["versions"].append(entry)

        if data["current_version"] is None:
            data["current_version"] = version

        self._save_prompt(data)
        logger.info(f"Registered prompt '{name}' version {version}")

    def get(self, name: str, version: str | None = None) -> dict | None:
        """Get a specific version or the current version of a prompt."""
        data = self._load_prompt(name)
        if not data["versions"]:
            return None

        if version:
            for v in data["versions"]:
                if v["version"] == version:
                    return {"name": name, **v}
            return None

        current = data["current_version"]
        for v in data["versions"]:
            if v["version"] == current:
                return {"name": name, **v}
        return None

    def list_versions(self, name: str) -> list[dict]:
        """List all versions of a prompt."""
        data = self._load_prompt(name)
        return [
            {
                "version": v["version"],
                "metadata": v["metadata"],
                "created_at": v["created_at"],
                "updated_at": v["updated_at"],
                "is_current": v["version"] == data["current_version"],
            }
            for v in data["versions"]
        ]

    def list_all(self) -> list[dict]:
        """List all registered prompts."""
        results = []
        for path in self.storage_dir.glob("*.json"):
            data = self._load_prompt(path.stem)
            current = data.get("current_version")
            results.append({
                "name": data["name"],
                "current_version": current,
                "version_count": len(data["versions"]),
            })
        return results

    def compare(self, name: str, v1: str, v2: str) -> dict:
        """Diff two versions of a prompt."""
        data = self._load_prompt(name)

        t1, t2 = None, None
        for v in data["versions"]:
            if v["version"] == v1:
                t1 = v["template"]
            if v["version"] == v2:
                t2 = v["template"]

        if t1 is None or t2 is None:
            raise ValueError(f"Version not found: {v1 if t1 is None else v2}")

        diff = list(difflib.unified_diff(
            t1.splitlines(keepends=True),
            t2.splitlines(keepends=True),
            fromfile=f"v{v1}",
            tofile=f"v{v2}",
        ))

        return {
            "name": name,
            "v1": v1,
            "v2": v2,
            "template_v1": t1,
            "template_v2": t2,
            "diff": "".join(diff),
            "changed": t1 != t2,
        }

    def rollback(self, name: str, version: str) -> None:
        """Set a version as the current version."""
        data = self._load_prompt(name)
        found = any(v["version"] == version for v in data["versions"])
        if not found:
            raise ValueError(f"Version '{version}' not found for prompt '{name}'")

        data["current_version"] = version
        self._save_prompt(data)
        logger.info(f"Rolled back prompt '{name}' to version {version}")

    def delete_version(self, name: str, version: str) -> None:
        """Remove a specific version."""
        data = self._load_prompt(name)
        data["versions"] = [v for v in data["versions"] if v["version"] != version]
        if data["current_version"] == version:
            data["current_version"] = (
                data["versions"][-1]["version"] if data["versions"] else None
            )
        self._save_prompt(data)
