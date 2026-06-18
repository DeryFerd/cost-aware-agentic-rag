"""Download SEC 10-K filings from EDGAR."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from src.config import settings

HEADERS = {
    "User-Agent": "DeryFerd ResearchBot deryferd@example.com",
    "Accept": "application/json",
}

# Target companies (CIK without leading zeros, ticker, name)
TARGET_COMPANIES = [
    ("789019", "MSFT", "Microsoft"),
    ("1018724", "AMZN", "Amazon"),
    ("1326801", "META", "Meta Platforms"),
    ("1652044", "GOOG", "Alphabet"),
    ("1318605", "TSLA", "Tesla"),
    ("320193", "AAPL", "Apple"),
    ("1045810", "NVDA", "NVIDIA"),
]


def _get_filing_accessions(cik: str, form_type: str = "10-K") -> list[dict]:
    """Get filing accessions from EDGAR XBRL API."""
    cik_padded = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

    try:
        resp = httpx.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])

        filings = []
        for form, date, acc in zip(forms, dates, accessions, strict=False):
            if form == form_type:
                try:
                    year = int(date[:4])
                    filings.append({
                        "date": date,
                        "year": year,
                        "accession": acc,
                        "form_type": form_type,
                    })
                except (ValueError, IndexError):
                    pass

        return filings[:5]

    except Exception as e:
        print(f"  Warning: Could not fetch filings for CIK {cik}: {e}")
        return []


def _download_filing_document(cik: str, accession: str, dest: Path) -> Path | None:
    """Download the primary filing document."""
    acc_no_dashes = accession.replace("-", "")

    # Try to get the filing index
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_no_dashes}/{accession}-index.htm"

    try:
        resp = httpx.get(index_url, headers=HEADERS, timeout=30, follow_redirects=True)
        resp.raise_for_status()

        # Find primary document
        import re
        # Look for the primary document link (usually .htm or .html)
        pattern = r'href="([^"]*\.(?:htm|html))"'
        matches = re.findall(pattern, resp.text)

        for match in matches:
            # Skip index pages
            if "index" in match.lower():
                continue

            # Build full URL
            if not match.startswith("http"):
                if match.startswith("/"):
                    doc_url = f"https://www.sec.gov{match}"
                else:
                    doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_no_dashes}/{match}"
            else:
                doc_url = match

            # Download the document
            try:
                doc_resp = httpx.get(doc_url, headers=HEADERS, timeout=60, follow_redirects=True)
                doc_resp.raise_for_status()
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(doc_resp.content)
                return dest
            except Exception:
                continue

    except Exception as e:
        print(f"  Warning: Could not fetch filing index: {e}")

    return None


def download_company_filings(
    ticker: str,
    cik: str,
    years: list[int] | None = None,
) -> list[Path]:
    """Download all 10-K filings for a company."""
    if years is None:
        years = [2022, 2023, 2024]

    company_dir = settings.raw_dir / ticker
    downloaded: list[Path] = []

    # Get filing list
    filings = _get_filing_accessions(cik)

    for filing in filings:
        year = filing["year"]
        if year not in years:
            continue

        dest = company_dir / str(year) / f"{ticker}_{year}_10K.html"
        result = _download_filing_document(cik, filing["accession"], dest)

        if result:
            downloaded.append(result)
            print(f"    Downloaded {year}")

        time.sleep(0.25)  # SEC rate limit (4 req/sec)

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
