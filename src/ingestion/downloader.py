"""Download SEC 10-K filings from EDGAR."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from src.config import settings

EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
HEADERS = {"User-Agent": "DeryFerd ResearchBot contact@example.com"}

# Target companies (CIK, ticker, name)
TARGET_COMPANIES = [
    ("789019", "MSFT", "Microsoft"),
    ("1018724", "AMZN", "Amazon"),
    ("1326801", "META", "Meta Platforms"),
    ("1652044", "GOOG", "Alphabet"),
    ("1318605", "TSLA", "Tesla"),
]


def _get_filing_index(cik: str, form_type: str = "10-K") -> list[dict]:
    """Get filing index from EDGAR."""
    # Clean CIK (remove leading zeros)
    cik_clean = cik.lstrip("0")
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_clean}&type=10-K&dateb=&owner=include&count=10&search_text=&action=getcompany"
    
    results = []
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        # Parse the HTML to find filing links
        text = resp.text
        # Find filing entries
        import re
        # Look for filing links in the format /Archives/edgar/data/...
        pattern = r'/Archives/edgar/data/\d+/\d+-\d+-\d+/'
        matches = re.findall(pattern, text)
        for match in matches[:5]:  # Limit to 5 most recent
            filing_url = f"https://www.sec.gov{match}"
            results.append({"url": filing_url, "form_type": form_type})
    except Exception as e:
        print(f"  Warning: Could not fetch index for CIK {cik}: {e}")
    
    return results


def _download_filing(url: str, dest: Path) -> Path | None:
    """Download a single filing to disk."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return dest
    except Exception as e:
        print(f"  Warning: Failed to download {url}: {e}")
        return None


def download_company_filings(
    ticker: str,
    cik: str,
    years: list[int] | None = None,
) -> list[Path]:
    """Download all 10-K filings for a company."""
    if years is None:
        years = list(range(2020, 2025))

    company_dir = settings.raw_dir / ticker
    downloaded: list[Path] = []

    # Use EDGAR full-text search API
    for year in years:
        search_url = f"https://efts.sec.gov/LATEST/search-index?q=%2210-K%22&forms=10-K&dateRange=custom&startdt={year}-01-01&enddt={year}-12-31&entities={cik}"
        
        try:
            resp = httpx.get(search_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            # Get filing URLs from search results
            hits = data.get("hits", {}).get("hits", [])
            for hit in hits[:1]:  # Take first filing per year
                source = hit.get("_source", {})
                filing_url = source.get("file_num", "")
                if filing_url and filing_url.startswith("http"):
                    dest = company_dir / str(year) / "filing.html"
                    result = _download_filing(filing_url, dest)
                    if result:
                        downloaded.append(result)
        except Exception:
            pass
        
        time.sleep(0.1)  # SEC rate limit

    return downloaded


def download_sample_dataset() -> dict[str, list[Path]]:
    """Download a sample dataset of SEC 10-K filings."""
    dataset: dict[str, list[Path]] = {}

    for cik, ticker, name in TARGET_COMPANIES:
        print(f"[DOWNLOAD] {name} ({ticker}) 10-K filings...")
        paths = download_company_filings(ticker, cik)
        dataset[ticker] = paths
        print(f"  OK: {len(paths)} filings")

    return dataset


if __name__ == "__main__":
    dataset = download_sample_dataset()
    total = sum(len(v) for v in dataset.values())
    print(f"\nTotal: {total} filings from {len(dataset)} companies")
