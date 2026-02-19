"""Compound analysis tools combining multiple Japan finance data sources.

These tools provide high-value analysis that would require 3-5 sequential
MCP calls if done individually.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypedDict, cast

from loguru import logger

from japanfinance_agent import adapters

_TASK_TIMEOUT = 90.0  # Per-task timeout in seconds (EDINET XBRL parsing can take 60s+)


async def _with_timeout(coro: Any, timeout: float = _TASK_TIMEOUT) -> Any:
    """Wrap a coroutine with a timeout, returning the error on timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return TimeoutError(f"timed out after {timeout}s")


class CompanyAnalysis(TypedDict):
    """Result of analyze_company."""

    code: str
    edinet_code: str | None
    company_name: str | None
    statements: dict[str, Any] | None
    disclosures: list[dict[str, Any]]
    stock_price: dict[str, Any] | None
    sources_used: list[str]


class MacroSnapshot(TypedDict):
    """Result of macro_snapshot."""

    estat_data: list[dict[str, Any]]
    sources_used: list[str]


class EarningsEntry(TypedDict):
    """Single company entry in earnings monitor."""

    code: str
    company_name: str | None
    disclosures: list[dict[str, Any]]
    metrics: dict[str, Any] | None


class EarningsMonitor(TypedDict):
    """Result of earnings_monitor."""

    companies: list[EarningsEntry]
    total_disclosures: int
    sources_used: list[str]


async def analyze_company(
    code: str,
    *,
    edinet_code: str | None = None,
    period: str | None = None,
    disclosure_limit: int = 10,
) -> CompanyAnalysis:
    """Comprehensive company analysis combining EDINET + TDNET + stock.

    Fetches financial statements, recent disclosures, and stock price data
    in parallel.

    Args:
        code: 4-digit stock code (e.g. "7203").
        edinet_code: Optional EDINET code (e.g. "E02144"). If not provided,
            searches for it using the stock code.
        period: Fiscal period year for EDINET statements.
        disclosure_limit: Max TDNET disclosures to fetch.

    Returns:
        CompanyAnalysis with data from all available sources.
    """
    sources_used: list[str] = []
    company_name: str | None = None

    # Resolve edinet_code if not provided
    if edinet_code is None:
        companies = await adapters.search_companies_edinet(code)
        if companies:
            edinet_code = companies[0]["edinet_code"]
            company_name = companies[0]["name"]

    # Parallel fetch from all sources
    tasks: dict[str, Any] = {}

    if edinet_code:
        tasks["statements"] = _with_timeout(
            adapters.get_company_statements(edinet_code, period=period)
        )

    tasks["disclosures"] = _with_timeout(
        adapters.get_company_disclosures(code, limit=disclosure_limit)
    )
    tasks["stock_price"] = _with_timeout(adapters.get_stock_price(code))

    # Run all in parallel (each task has its own timeout)
    keys = list(tasks.keys())
    results_list = await asyncio.gather(*tasks.values(), return_exceptions=True)
    results = dict(zip(keys, results_list, strict=True))

    # Process results — narrow types from gather's BaseException union
    raw_stmt = results.get("statements")
    statements: dict[str, Any] | None = None
    if isinstance(raw_stmt, BaseException):
        logger.warning(f"Statements fetch error: {raw_stmt}")
    elif raw_stmt is not None:
        statements = cast("dict[str, Any]", raw_stmt)
        sources_used.append("edinet")
        company_name = company_name or statements.get("company_name")

    raw_disc = results.get("disclosures", [])
    disclosures: list[dict[str, Any]] = []
    if isinstance(raw_disc, BaseException):
        logger.warning(f"Disclosures fetch error: {raw_disc}")
    else:
        disclosures = cast("list[dict[str, Any]]", raw_disc)
    if disclosures:
        sources_used.append("tdnet")
        company_name = company_name or disclosures[0].get("company_name")

    raw_stock = results.get("stock_price")
    stock_price: dict[str, Any] | None = None
    if isinstance(raw_stock, BaseException):
        logger.warning(f"Stock price error: {raw_stock}")
    elif raw_stock is not None:
        stock_price = cast("dict[str, Any]", raw_stock)
        sources_used.append("yfinance")

    return CompanyAnalysis(
        code=code,
        edinet_code=edinet_code,
        company_name=company_name,
        statements=statements,
        disclosures=disclosures,
        stock_price=stock_price,
        sources_used=sources_used,
    )


async def macro_snapshot(
    *,
    keyword: str = "GDP",
    estat_limit: int = 5,
) -> MacroSnapshot:
    """Macro economic snapshot from e-Stat government statistics.

    Args:
        keyword: e-Stat search keyword (e.g. "GDP", "CPI", "雇用").
        estat_limit: Max e-Stat tables.

    Returns:
        MacroSnapshot with data from available sources.
    """
    sources_used: list[str] = []

    try:
        raw_estat = await _with_timeout(adapters.get_estat_data(keyword, limit=estat_limit))
    except Exception as e:
        logger.warning(f"e-Stat error: {e}")
        raw_estat = []

    estat_data: list[dict[str, Any]] = []
    if isinstance(raw_estat, BaseException):
        logger.warning(f"e-Stat error: {raw_estat}")
    else:
        estat_data = cast("list[dict[str, Any]]", raw_estat)
    if estat_data:
        sources_used.append("estat")

    return MacroSnapshot(
        estat_data=estat_data,
        sources_used=sources_used,
    )


async def earnings_monitor(
    codes: list[str],
    *,
    disclosure_limit: int = 5,
) -> EarningsMonitor:
    """Monitor earnings and disclosures for a watchlist of companies.

    Fetches TDNET disclosures for each company in parallel.

    Args:
        codes: List of 4-digit stock codes.
        disclosure_limit: Max disclosures per company.

    Returns:
        EarningsMonitor with disclosure data for all companies.
    """
    sources_used: list[str] = []
    total_disclosures = 0

    # Fetch disclosures for all companies in parallel (each with timeout)
    task_list = [
        _with_timeout(adapters.get_company_disclosures(code, limit=disclosure_limit))
        for code in codes
    ]
    results = await asyncio.gather(*task_list, return_exceptions=True)

    companies: list[EarningsEntry] = []
    for code, result in zip(codes, results, strict=True):
        disclosures: list[dict[str, Any]]
        if isinstance(result, BaseException):
            logger.warning(f"Fetch failed for {code}: {result}")
            disclosures = []
        else:
            disclosures = result

        company_name: str | None = None
        if disclosures:
            company_name = disclosures[0].get("company_name")
            total_disclosures += len(disclosures)

        companies.append(
            EarningsEntry(
                code=code,
                company_name=company_name,
                disclosures=disclosures,
                metrics=None,
            )
        )

    if total_disclosures > 0:
        sources_used.append("tdnet")

    return EarningsMonitor(
        companies=companies,
        total_disclosures=total_disclosures,
        sources_used=sources_used,
    )
