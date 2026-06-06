"""Tests for the ingestion pipeline."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import settings


def test_settings_load():
    assert settings.ollama_host == "https://ollama.com"
    assert settings.embedding_model == "nomic-embed-text"
    assert settings.raw_dir.exists()


def test_directories_created():
    assert settings.raw_dir.exists()
    assert settings.processed_dir.exists()
    assert settings.indexes_dir.exists()
    assert settings.eval_dir.exists()
