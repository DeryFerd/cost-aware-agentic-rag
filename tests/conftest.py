"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests requiring live services")


@pytest.fixture(scope="session")
def project_root_dir():
    """Return project root directory."""
    return project_root


@pytest.fixture(scope="session")
def settings():
    """Load project settings."""
    from src.config import settings as _settings
    return _settings


@pytest.fixture
def mock_llm():
    """Mock OllamaClient for tests that don't need real LLM."""
    with patch("src.generation.llm_client.OllamaClient") as mock:
        instance = MagicMock()
        instance.chat.return_value = MagicMock(
            content="Test response",
            model="gemma3:4b",
            tokens_in=50,
            tokens_out=100,
            latency_ms=500.0,
            cost_usd=0.001,
            raw={"message": {"content": "Test response"}},
        )
        instance.classify_complexity.return_value = "simple"
        instance._estimate_cost.return_value = 0.001
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_redis():
    """Mock Redis cache for tests."""
    with patch("src.database.cache.cache") as mock:
        mock.get.return_value = None
        mock.set.return_value = True
        mock.delete.return_value = True
        yield mock


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore for tests."""
    with patch("src.retrieval.vector_store.VectorStore") as mock:
        instance = MagicMock()
        instance.count.return_value = 2075
        instance.query.return_value = []
        mock.return_value = instance
        yield instance


@pytest.fixture
def sample_context():
    """Sample context string for testing."""
    return (
        "[MSFT 2024] Microsoft Corporation reported revenue of $245.1 billion for fiscal year 2024.\n\n"
        "---\n\n"
        "[AMZN 2024] Amazon.com, Inc. reported revenue of $574.0 billion for fiscal year 2024.\n\n"
        "---\n\n"
        "[TSLA 2024] Tesla, Inc. reported revenue of $97.7 billion for fiscal year 2024."
    )


@pytest.fixture
def sample_query():
    """Sample financial query for testing."""
    return "What was Microsoft's revenue in 2024?"
