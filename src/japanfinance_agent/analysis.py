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


def _safe_result(data: dict[str, Any], key: str, label: str) -> Any | None:
    """Return data[key] if not a BaseException, else log warning and return None."""
    raw = data.get(key)
    if isinstance(raw, BaseException):
        logger.warning(f"{label}: {raw}")
        return None
    return raw


def _process_statements(
    data: dict[str, Any], sources_used: list[str]
) -> tuple[dict[str, Any] | None, str | None]:
    """Process statements from raw gather results.

    Returns:
        (statements dict or None, company_name candidate or None).
    """
    raw = _safe_result(data, "statements", "Statements fetch error")
    if raw is None:
        return None, None
    statements = cast("dict[str, Any]", raw)
    sources_used.append("edinet")
    return statements, statements.get("company_name")


def _process_disclosures(
    data: dict[str, Any], sources_used: list[str]
) -> tuple[list[dict[str, Any]], str | None]:
    """Process disclosures from raw gather results.

    Returns:
        (disclosures list, company_name candidate or None).
    """
    raw = _safe_result(data, "disclosures", "Disclosures fetch error")
    if raw is None:
        return [], None
    disclosures = cast("list[dict[str, Any]]", raw)
    if disclosures:
        sources_used.append("tdnet")
        return disclosures, disclosures[0].get("company_name")
    return disclosures, None


def _process_stock_price(data: dict[str, Any], sources_used: list[str]) -> dict[str, Any] | None:
    """Process stock price from raw gather results."""
    raw = _safe_result(data, "stock_price", "Stock price error")
    if raw is None:
        return None
    stock_price = cast("dict[str, Any]", raw)
    sources_used.append("yfinance")
    return stock_price


def _build_analysis_report(
    data: dict[str, Any],
    *,
    code: str,
    edinet_code: str | None,
    company_name: str | None,
) -> CompanyAnalysis:
    """Build CompanyAnalysis from raw gathered results.

    Args:
        data: Dict mapping source names to gathered results
            (values may be BaseException from asyncio.gather).
        code: 4-digit stock code.
        edinet_code: EDINET code (if resolved).
        company_name: Company name (if resolved from search).

    Returns:
        CompanyAnalysis with processed data from all sources.
    """
    sources_used: list[str] = []

    statements, stmt_name = _process_statements(data, sources_used)
    disclosures, disc_name = _process_disclosures(data, sources_used)
    stock_price = _process_stock_price(data, sources_used)

    company_name = company_name or stmt_name or disc_name

    return CompanyAnalysis(
        code=code,
        edinet_code=edinet_code,
        company_name=company_name,
        statements=statements,
        disclosures=disclosures,
        stock_price=stock_price,
        sources_used=sources_used,
    )


async def _resolve_edinet_code(
    code: str, edinet_code: str | None
) -> tuple[str | None, str | None]:
    """Resolve EDINET code for a stock code if not already provided.

    Uses CompanyRegistry.resolve() for auto-detection of identifier type,
    with fallback to EDINET search.

    Returns:
        (edinet_code, company_name) — company_name is set only when
        edinet_code was resolved via search.
    """
    if edinet_code is not None:
        return edinet_code, None
    result = await adapters.resolve_company(code)
    if result:
        return result["edinet_code"], result["name"]
    return None, None


async def _fetch_all_sources(
    edinet_code: str | None,
    code: str,
    *,
    period: str | None,
    disclosure_limit: int,
) -> dict[str, Any]:
    """Build and run parallel fetch tasks for all data sources.

    Returns:
        Dict mapping source names to results (values may be BaseException).
    """
    tasks: dict[str, Any] = {}
    if edinet_code:
        tasks["statements"] = _with_timeout(
            adapters.get_company_statements(edinet_code, period=period)
        )
    tasks["disclosures"] = _with_timeout(
        adapters.get_company_disclosures(code, limit=disclosure_limit)
    )
    tasks["stock_price"] = _with_timeout(adapters.get_stock_price(code))

    keys = list(tasks.keys())
    results_list = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return dict(zip(keys, results_list, strict=True))


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
    edinet_code, company_name = await _resolve_edinet_code(code, edinet_code)
    results = await _fetch_all_sources(
        edinet_code, code, period=period, disclosure_limit=disclosure_limit
    )
    return _build_analysis_report(
        results, code=code, edinet_code=edinet_code, company_name=company_name
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
    except (OSError, ImportError, ValueError, KeyError, TypeError, AttributeError) as e:
        # adapters.get_estat_data handles httpx/connection/timeout internally;
        # OSError covers residual network errors, the rest cover broken installs
        # and data-format mismatches from the dynamically-imported estat_mcp.
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


def _process_single_earnings(code: str, result: Any) -> tuple[EarningsEntry, int]:
    """Process a single company's fetch result into an EarningsEntry.

    Returns:
        (entry, disclosure_count) tuple.
    """
    disclosures: list[dict[str, Any]]
    if isinstance(result, BaseException):
        logger.warning(f"Fetch failed for {code}: {result}")
        disclosures = []
    else:
        disclosures = result

    company_name: str | None = None
    count = 0
    if disclosures:
        company_name = disclosures[0].get("company_name")
        count = len(disclosures)

    entry = EarningsEntry(
        code=code,
        company_name=company_name,
        disclosures=disclosures,
        metrics=None,
    )
    return entry, count


def _build_earnings_entries(
    codes: list[str], results: list[Any]
) -> tuple[list[EarningsEntry], int]:
    """Build EarningsEntry list from parallel fetch results.

    Returns:
        (companies list, total_disclosures count).
    """
    companies: list[EarningsEntry] = []
    total_disclosures = 0
    for code, result in zip(codes, results, strict=True):
        entry, count = _process_single_earnings(code, result)
        companies.append(entry)
        total_disclosures += count
    return companies, total_disclosures


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
    task_list = [
        _with_timeout(adapters.get_company_disclosures(code, limit=disclosure_limit))
        for code in codes
    ]
    results = await asyncio.gather(*task_list, return_exceptions=True)

    companies, total_disclosures = _build_earnings_entries(codes, results)

    sources_used: list[str] = []
    if total_disclosures > 0:
        sources_used.append("tdnet")

    return EarningsMonitor(
        companies=companies,
        total_disclosures=total_disclosures,
        sources_used=sources_used,
    )
