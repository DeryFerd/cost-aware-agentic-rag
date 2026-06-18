"""Compare SEC filings across years and companies."""

from __future__ import annotations

import re
from typing import Any

from src.retrieval.hybrid import HybridRetriever


def _extract_numeric(text: str, metric: str) -> float | None:
    """Try to extract a numeric value related to a metric from text."""
    patterns: list[re.Pattern] = []

    if metric in ("revenue", "total_revenue", "net_revenue"):
        patterns = [
            re.compile(r"revenue[sd]*\s+(?:of\s+)?\$?\s*([\d,]+(?:\.\d+)?)\s*(?:billion|B)", re.I),
            re.compile(r"revenue[sd]*\s+(?:of\s+)?\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|M)", re.I),
            re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:billion|B).*?revenue", re.I),
            re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|M).*?revenue", re.I),
        ]
    elif metric in ("employees", "num_employees", "headcount"):
        patterns = [
            re.compile(r"([\d,]+(?:\.\d+)?)\s+(?:thousand|,000)\s+employees", re.I),
            re.compile(r"employees?\s+(?:of\s+)?([\d,]+)", re.I),
            re.compile(r"approximately\s+([\d,]+)\s+employees", re.I),
        ]
    elif metric in ("net_income", "net_earnings", "profit"):
        patterns = [
            re.compile(r"net\s+income[sd]*\s+(?:of\s+)?\$?\s*([\d,]+(?:\.\d+)?)\s*(?:billion|B)", re.I),
            re.compile(r"net\s+income[sd]*\s+(?:of\s+)?\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|M)", re.I),
        ]
    elif metric in ("total_assets", "assets"):
        patterns = [
            re.compile(r"total\s+assets\s+(?:of\s+)?\$?\s*([\d,]+(?:\.\d+)?)\s*(?:billion|B)", re.I),
            re.compile(r"total\s+assets\s+(?:of\s+)?\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|M)", re.I),
        ]
    else:
        patterns = [
            re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:billion|B)", re.I),
            re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|M)", re.I),
            re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:thousand|,000)", re.I),
        ]

    for pat in patterns:
        m = pat.search(text)
        if m:
            val = m.group(1).replace(",", "")
            try:
                num = float(val)
                if "million" in pat.pattern.lower() or ",000" in pat.pattern:
                    num *= 1_000_000
                elif "thousand" in pat.pattern.lower():
                    num *= 1_000
                return num
            except ValueError:
                continue
    return None


def _classify_trend(deltas: list[dict[str, Any]]) -> str:
    """Classify overall trend from year-over-year deltas."""
    if not deltas:
        return "stable"
    changes = [d["pct_change"] for d in deltas if d["pct_change"] is not None]
    if not changes:
        return "stable"
    avg = sum(changes) / len(changes)
    if avg > 5:
        return "improving"
    if avg < -5:
        return "declining"
    return "stable"


class FilingComparator:
    """Compare SEC 10-K filings across years and companies."""

    def __init__(self) -> None:
        self.retriever = HybridRetriever()

    def _fetch_chunks(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Retrieve chunks and return as list of dicts."""
        results = self.retriever.retrieve(query, top_k=top_k, use_filters=True)
        return [
            {
                "text": r.text[:1000],
                "ticker": r.metadata.get("ticker", "") if r.metadata else "",
                "year": r.metadata.get("year", "") if r.metadata else "",
            }
            for r in results
        ]

    def compare_years(self, ticker: str, metric: str, years: list[str]) -> dict[str, Any]:
        """Compare a single metric across multiple years for one ticker.

        Returns structured dict with data_points, deltas, and trend.
        """
        data_points: list[dict[str, Any]] = []

        for year in sorted(years):
            chunks = self._fetch_chunks(f"{ticker} {metric} {year}", top_k=3)
            ticker_chunks = [c for c in chunks if c["ticker"].upper() == ticker.upper()]
            if not ticker_chunks:
                ticker_chunks = chunks

            combined_text = " ".join(c["text"] for c in ticker_chunks)
            value = _extract_numeric(combined_text, metric)

            data_points.append({
                "year": year,
                "value": value,
                "text": combined_text[:500] if combined_text else "",
            })

        # Compute deltas
        deltas: list[dict[str, Any]] = []
        for i in range(1, len(data_points)):
            prev = data_points[i - 1]
            curr = data_points[i]
            change = None
            pct_change = None
            if prev["value"] is not None and curr["value"] is not None:
                change = curr["value"] - prev["value"]
                if prev["value"] != 0:
                    pct_change = round((change / abs(prev["value"])) * 100, 2)
            deltas.append({
                "year": f"{prev['year']}->{curr['year']}",
                "change": change,
                "pct_change": pct_change,
            })

        trend = _classify_trend(deltas)

        return {
            "ticker": ticker,
            "metric": metric,
            "data_points": data_points,
            "deltas": deltas,
            "trend": trend,
        }

    def compare_companies(self, tickers: list[str], metric: str, year: str) -> dict[str, Any]:
        """Compare the same metric across companies for one year.

        Returns structured dict with rankings.
        """
        company_data: list[dict[str, Any]] = []

        for ticker in tickers:
            chunks = self._fetch_chunks(f"{ticker} {metric} {year}", top_k=3)
            combined_text = " ".join(c["text"] for c in chunks)
            value = _extract_numeric(combined_text, metric)

            company_data.append({
                "ticker": ticker,
                "value": value,
                "text": combined_text[:500] if combined_text else "",
            })

        # Rank by value (highest first), None values at the end
        ranked = sorted(
            company_data,
            key=lambda c: c["value"] if c["value"] is not None else float("-inf"),
            reverse=True,
        )

        for i, entry in enumerate(ranked):
            entry["rank"] = i + 1

        return {
            "metric": metric,
            "year": year,
            "rankings": ranked,
        }
