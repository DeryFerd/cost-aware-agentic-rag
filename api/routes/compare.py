"""Compare filings endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents.compare import FilingComparator

logger = logging.getLogger(__name__)
router = APIRouter()


class CompareYearsRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, description="Company ticker")
    metric: str = Field(..., min_length=1, description="Metric: revenue, employees, net_income, etc.")
    years: list[str] = Field(..., min_length=2, description="Years to compare (e.g. ['2022','2023','2024'])")


class CompareCompaniesRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=2, description="Company tickers to compare")
    metric: str = Field(..., min_length=1, description="Metric: revenue, employees, net_income, etc.")
    year: str = Field(..., pattern=r"^\d{4}$", description="Filing year")


@router.post("/compare/years")
def compare_years(req: CompareYearsRequest) -> dict:
    """Compare a company across multiple years."""
    try:
        comparator = FilingComparator()
        result = comparator.compare_years(
            ticker=req.ticker.upper(),
            metric=req.metric,
            years=req.years,
        )
        return result
    except Exception as e:
        logger.error(f"Year comparison failed: {e}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}") from e


@router.post("/compare/companies")
def compare_companies(req: CompareCompaniesRequest) -> dict:
    """Compare multiple companies for one year."""
    try:
        comparator = FilingComparator()
        result = comparator.compare_companies(
            tickers=[t.upper() for t in req.tickers],
            metric=req.metric,
            year=req.year,
        )
        return result
    except Exception as e:
        logger.error(f"Company comparison failed: {e}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}") from e
