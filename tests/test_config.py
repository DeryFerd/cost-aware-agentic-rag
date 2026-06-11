"""Unit tests for configuration and golden set."""

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import settings


def test_settings_load():
    assert settings.ollama_host is not None
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
    assert settings.ollama_simple_model == "gemma3:4b"
    assert settings.ollama_complex_model == "gemma3:27b"


def test_directories_created():
    assert settings.raw_dir.exists()
    assert settings.processed_dir.exists()
    assert settings.indexes_dir.exists()
    assert settings.eval_dir.exists()


@pytest.mark.integration
def test_sample_data_exists():
    companies = ["MSFT", "AMZN", "META", "GOOG", "TSLA"]
    for ticker in companies:
        company_dir = settings.raw_dir / ticker
        assert company_dir.exists(), f"Missing directory for {ticker}"
        years = list(company_dir.iterdir())
        assert len(years) > 0, f"No year directories for {ticker}"


def test_golden_set():
    from src.eval.golden_set import get_golden_set, get_golden_set_by_company

    golden_set = get_golden_set()
    assert len(golden_set) > 0

    msft_queries = get_golden_set_by_company("MSFT")
    assert len(msft_queries) > 0
    assert all(q["company"] == "MSFT" for q in msft_queries)


def test_retrieval_filters():
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

    assert extract_ticker("What was Microsoft revenue?") == "MSFT"
    assert extract_ticker("Tell me about Tesla") == "TSLA"
    assert extract_ticker("Amazon AWS") == "AMZN"
    assert extract_year("Revenue in 2024") == "2024"
    assert extract_year("2023 financials") == "2023"
    assert extract_year("No year here") is None
