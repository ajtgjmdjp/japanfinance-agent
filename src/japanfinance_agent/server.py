"""MCP server for japanfinance-agent.

Provides compound analysis tools that combine multiple Japan finance data
sources into single, high-value operations.
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

from fastmcp import FastMCP
from loguru import logger
from pydantic import BeforeValidator

from japanfinance_agent import adapters
from japanfinance_agent.analysis import analyze_company, earnings_monitor, macro_snapshot


def _coerce_str(v: Any) -> str | None:
    """Coerce int to str — MCP clients may send numeric values as int."""
    if v is None:
        return None
    return str(v)


_CODE_RE = re.compile(r"^\d{4}$")
_EDINET_CODE_RE = re.compile(r"^E\d{5}$")
_PERIOD_RE = re.compile(r"^\d{4}$")
_MAX_WATCHLIST = 20

mcp = FastMCP(
    "japanfinance-agent",
    instructions=(
        "Compound analysis tools for Japanese financial data. "
        "Combines EDINET, TDNET, e-Stat, and stock price data."
    ),
)


@mcp.tool()
async def analyze_japanese_company(
    code: Annotated[str, BeforeValidator(_coerce_str)],
    edinet_code: Annotated[str | None, BeforeValidator(_coerce_str)] = None,
    period: Annotated[str | None, BeforeValidator(_coerce_str)] = None,
) -> str:
    """Comprehensive analysis of a Japanese company.

    Combines EDINET financial statements, TDNET disclosures,
    and stock price data into a single view.

    Args:
        code: 4-digit stock code (e.g. "7203" for Toyota).
        edinet_code: Optional EDINET code (e.g. "E02144"). Auto-resolved if omitted.
        period: Filing year for EDINET statements (e.g. "2025").
    """
    if not _CODE_RE.match(code):
        return json.dumps({"error": f"Invalid stock code: {code!r} (expected 4 digits)"})
    if edinet_code is not None and not _EDINET_CODE_RE.match(edinet_code):
        return json.dumps(
            {"error": f"Invalid EDINET code: {edinet_code!r} (expected E + 5 digits)"}
        )
    if period is not None and not _PERIOD_RE.match(period):
        return json.dumps({"error": f"Invalid period: {period!r} (expected 4-digit year)"})

    logger.info(f"Analyzing company: {code}")
    result = await analyze_company(
        code,
        edinet_code=edinet_code,
        period=period,
    )
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
async def get_macro_snapshot(
    keyword: str = "GDP",
) -> str:
    """Macro economic snapshot for Japan.

    Searches e-Stat government statistics for the given keyword.

    Args:
        keyword: Search keyword for e-Stat (e.g. "GDP", "CPI", "雇用", "物価").
    """
    if not keyword or not keyword.strip():
        return json.dumps({"error": "keyword must not be empty"})
    if len(keyword) > 200:
        return json.dumps({"error": f"keyword too long: {len(keyword)} chars (max 200)"})

    logger.info(f"Macro snapshot: keyword={keyword}")
    result = await macro_snapshot(keyword=keyword)
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
async def monitor_earnings(
    codes: list[str],
) -> str:
    """Monitor earnings and disclosures for a watchlist of companies.

    Fetches recent TDNET disclosures for multiple companies.

    Args:
        codes: List of 4-digit stock codes (e.g. ["7203", "6758", "6861"]).
    """
    if not codes:
        return json.dumps({"error": "codes list must not be empty"})
    if len(codes) > _MAX_WATCHLIST:
        return json.dumps({"error": f"Too many codes: {len(codes)} (max {_MAX_WATCHLIST})"})
    invalid = [c for c in codes if not _CODE_RE.match(c)]
    if invalid:
        return json.dumps({"error": f"Invalid stock codes: {invalid!r} (expected 4 digits each)"})

    logger.info(f"Monitoring {len(codes)} companies")
    result = await earnings_monitor(codes)
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
async def check_data_sources() -> str:
    """Check which Japan finance data sources are available and connected.

    Returns the status of each data source (installed, connected, or missing).
    """
    results = await adapters.test_connections()
    return json.dumps(results, ensure_ascii=False, indent=2)
