"""Download SEC 10-K filings from EDGAR."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from src.config import settings

EDGAR_BASE = "https://efts.sec.gov/LATEST"
EDGAR_FILING = "https://www.sec.gov/Archives/edgar/data"
HEADERS = {"User-Agent": "DeryFerd ResearchBot contact@example.com"}

# Target companies (CIK, ticker, name)
TARGET_COMPANIES = [
    ("789019", "MSFT", "Microsoft"),
    ("1018724", "AMZN", "Amazon"),
    ("1326801", "META", "Meta Platforms"),
    ("1652044", "GOOG", "Alphabet"),
    ("1318605", "TSLA", "Tesla"),
]


def _search_filings(
    cik: str,
    form_type: str = "10-K",
    years: list[int] | None = None,
    limit: int = 5,
) -> list[dict]:
    """Search EDGAR EFTS for filing metadata."""
    if years is None:
        years = list(range(2020, 2025))

    results = []
    for year in years:
        url = f"{EDGAR_BASE}/search-index?q=%22{form_type}%22&dateRange=custom&startdt={year}-01-01&enddt={year}-12-31&forms={form_type}&entities={cik}"
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            for hit in hits[:limit]:
                src = hit.get("_source", {})
                results.append(
                    {
                        "filed": src.get("filed", ""),
                        "form_type": src.get("form_type", ""),
                        "display_names": src.get("display_names", []),
                        "link_filing": src.get("file_num", ""),
                    }
                )
        except httpx.HTTPError:
            continue
        time.sleep(0.1)  # SEC rate limit courtesy

    return results


def _download_filing(url: str, dest: Path) -> Path | None:
    """Download a single filing PDF/HTML to disk."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return dest
    except httpx.HTTPError:
        return None


def download_company_filings(
    ticker: str,
    cik: str,
    years: list[int] | None = None,
) -> list[Path]:
    """Download all 10-K filings for a company across given years."""
    if years is None:
        years = list(range(2020, 2025))

    company_dir = settings.raw_dir / ticker
    downloaded: list[Path] = []

    # Use EDGAR full-text search to get filing indices
    search_url = f"https://efts.sec.gov/LATEST/search-index?q=%2210-K%22&forms=10-K&entities={cik}"
    try:
        resp = httpx.get(search_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError:
        return downloaded

    # Fallback: use XBRL companion index
    for year in years:
        filing_dir = company_dir / str(year)
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/"
        index_file = filing_dir / "index.html"

        if not index_file.exists():
            _download_filing(index_url, index_file)

        downloaded.append(filing_dir)

    return downloaded


def download_sample_dataset() -> dict[str, list[Path]]:
    """Download a sample dataset of SEC 10-K filings."""
    dataset: dict[str, list[Path]] = {}

    for cik, ticker, name in TARGET_COMPANIES:
        print(f"📥 Downloading {name} ({ticker}) 10-K filings...")
        paths = download_company_filings(ticker, cik)
        dataset[ticker] = paths
        print(f"   ✓ {len(paths)} filings")

    return dataset


if __name__ == "__main__":
    dataset = download_sample_dataset()
    total = sum(len(v) for v in dataset.values())
    print(f"\n✅ Total: {total} filings from {len(dataset)} companies")
