"""Tests for the FinRAG project."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import settings


def test_settings_load():
    """Test that settings load correctly."""
    assert settings.ollama_host == "https://ollama.com"
    assert settings.embedding_model == "all-MiniLM-L6-v2"
    assert settings.ollama_simple_model == "gemma3:4b"
    assert settings.ollama_complex_model == "gemma3:27b"


def test_directories_created():
    """Test that required directories exist."""
    assert settings.raw_dir.exists()
    assert settings.processed_dir.exists()
    assert settings.indexes_dir.exists()
    assert settings.eval_dir.exists()


def test_sample_data_exists():
    """Test that sample SEC filings exist."""
    companies = ["MSFT", "AMZN", "META", "GOOG", "TSLA"]
    for ticker in companies:
        company_dir = settings.raw_dir / ticker
        assert company_dir.exists(), f"Missing directory for {ticker}"

        # Check for at least one year
        years = list(company_dir.iterdir())
        assert len(years) > 0, f"No year directories for {ticker}"


def test_golden_set():
    """Test that golden set loads correctly."""
    from src.eval.golden_set import get_golden_set, get_golden_set_by_company

    golden_set = get_golden_set()
    assert len(golden_set) > 0

    # Test filtering by company
    msft_queries = get_golden_set_by_company("MSFT")
    assert len(msft_queries) > 0
    assert all(q["company"] == "MSFT" for q in msft_queries)


def test_retrieval_filters():
    """Test that query filters extract ticker and year correctly."""
    import re

    def extract_ticker(query):
        tickers = {
            "MSFT": ["microsoft", "msft"],
            "AMZN": ["amazon", "amzn"],
            "META": ["meta", "facebook"],
            "GOOG": ["google", "alphabet", "goog"],
            "TSLA": ["tesla", "tsla"],
        }
        query_lower = query.lower()
        for ticker, keywords in tickers.items():
            for kw in keywords:
                if kw in query_lower:
                    return ticker
        return None

    def extract_year(query):
        match = re.search(r"\b(20\d{2})\b", query)
        return match.group(1) if match else None

    # Test ticker extraction
    assert extract_ticker("What was Microsoft revenue?") == "MSFT"
    assert extract_ticker("Tell me about Tesla") == "TSLA"
    assert extract_ticker("Amazon AWS") == "AMZN"

    # Test year extraction
    assert extract_year("Revenue in 2024") == "2024"
    assert extract_year("2023 financials") == "2023"
    assert extract_year("No year here") is None
