"""Adapter layer for Japan finance MCP data sources.

Each adapter wraps a client from one of the 6 MCP packages (edinet-mcp,
tdnet-disclosure-mcp, estat-mcp, boj-mcp, stockprice-mcp).

All adapters gracefully handle missing packages — if a package is not installed,
the adapter returns None or empty results instead of raising ImportError.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from datetime import date


def _is_available(package: str) -> bool:
    """Check if a package is importable."""
    try:
        __import__(package)
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# EDINET adapter
# ---------------------------------------------------------------------------


async def get_company_statements(
    edinet_code: str,
    *,
    period: str | None = None,
) -> dict[str, Any] | None:
    """Fetch financial statements from EDINET.

    Returns a dict with keys: company_name, accounting_standard,
    income_statement, balance_sheet, cash_flow_statement, metrics.
    """
    if not _is_available("edinet_mcp"):
        logger.debug("edinet-mcp not installed, skipping")
        return None

    from datetime import datetime

    from edinet_mcp import EdinetClient, calculate_metrics

    # Default to previous fiscal year if not specified
    if period is None:
        now = datetime.now()
        period = str(now.year - 1) if now.month >= 7 else str(now.year - 2)

    try:
        async with EdinetClient() as client:
            stmt = await client.get_financial_statements(
                edinet_code=edinet_code,
                period=period,
            )
            metrics = calculate_metrics(stmt)

            return {
                "source": "edinet",
                "company_name": stmt.filing.company_name,
                "edinet_code": edinet_code,
                "accounting_standard": stmt.accounting_standard.value,
                "filing_date": str(stmt.filing.filing_date),
                "income_statement": stmt.income_statement.to_dicts()[:20],
                "balance_sheet": stmt.balance_sheet.to_dicts()[:20],
                "metrics": metrics,
            }
    except Exception as e:
        logger.warning(f"EDINET fetch failed for {edinet_code}: {e}")
        return None


async def search_companies_edinet(query: str) -> list[dict[str, Any]]:
    """Search companies via EDINET."""
    if not _is_available("edinet_mcp"):
        return []

    from edinet_mcp import EdinetClient

    try:
        async with EdinetClient() as client:
            companies = await client.search_companies(query)
            return [
                {
                    "edinet_code": c.edinet_code,
                    "name": c.name,
                    "ticker": c.ticker,
                }
                for c in companies[:10]
            ]
    except Exception as e:
        logger.warning(f"EDINET search failed: {e}")
        return []


# ---------------------------------------------------------------------------
# TDNET adapter
# ---------------------------------------------------------------------------


async def get_company_disclosures(
    code: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch recent disclosures for a company from TDNET."""
    if not _is_available("tdnet_disclosure_mcp"):
        logger.debug("tdnet-disclosure-mcp not installed, skipping")
        return []

    from tdnet_disclosure_mcp.client import TdnetClient

    try:
        async with TdnetClient() as client:
            result = await client.get_by_code(code, limit=limit)
            return [
                {
                    "source": "tdnet",
                    "pubdate": str(d.pubdate),
                    "company_name": d.company_name,
                    "title": d.title,
                    "category": d.category.value,
                    "document_url": d.document_url,
                }
                for d in result.disclosures
            ]
    except Exception as e:
        logger.warning(f"TDNET fetch failed for {code}: {e}")
        return []


async def get_latest_disclosures(limit: int = 20) -> list[dict[str, Any]]:
    """Fetch latest TDNET disclosures."""
    if not _is_available("tdnet_disclosure_mcp"):
        return []

    from tdnet_disclosure_mcp.client import TdnetClient

    try:
        async with TdnetClient() as client:
            result = await client.get_recent(limit=limit)
            return [
                {
                    "source": "tdnet",
                    "pubdate": str(d.pubdate),
                    "company_code": d.company_code,
                    "company_name": d.company_name,
                    "title": d.title,
                    "category": d.category.value,
                }
                for d in result.disclosures
            ]
    except Exception as e:
        logger.warning(f"TDNET latest fetch failed: {e}")
        return []



# ---------------------------------------------------------------------------
# News adapter (removed — returns empty list)
# ---------------------------------------------------------------------------


async def get_news(
    query: str | None = None,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch financial news headlines. (News source removed — returns empty list.)"""
    return []


# ---------------------------------------------------------------------------
# Stock price adapter
# ---------------------------------------------------------------------------


async def get_stock_price(
    code: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any] | None:
    """Fetch stock price data via yfinance (stockprice-mcp)."""
    if not _is_available("yfinance_mcp"):
        logger.debug("stockprice-mcp not installed, skipping")
        return None

    from yfinance_mcp.client import YfinanceClient

    client = YfinanceClient()
    try:
        result = await client.get_stock_price(
            code,
            start_date=start_date,
            end_date=end_date,
        )
        if result is None:
            return None
        return {
            "source": "yfinance",
            "code": result.code,
            "date": result.date,
            "close": result.close,
            "open": result.open,
            "high": result.high,
            "low": result.low,
            "volume": result.volume,
            "week52_high": result.week52_high,
            "week52_low": result.week52_low,
            "trailing_pe": result.trailing_pe,
            "price_to_book": result.price_to_book,
            "market_cap": result.market_cap,
        }
    except Exception as e:
        logger.warning(f"yfinance fetch failed for {code}: {e}")
        return None


# ---------------------------------------------------------------------------
# e-Stat adapter
# ---------------------------------------------------------------------------


async def get_estat_data(
    keyword: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search and fetch government statistics from e-Stat."""
    if not _is_available("estat_mcp"):
        logger.debug("estat-mcp not installed, skipping")
        return []

    from estat_mcp.client import EstatClient

    try:
        async with EstatClient() as client:
            tables = await client.search_stats(keyword=keyword, limit=limit)
            return [
                {
                    "source": "estat",
                    "stats_id": t.id,
                    "title": t.name,
                    "survey_date": t.survey_date,
                    "gov_org": t.organization,
                }
                for t in tables
            ]
    except Exception as e:
        logger.warning(f"e-Stat search failed: {e}")
        return []


# ---------------------------------------------------------------------------
# BOJ adapter
# ---------------------------------------------------------------------------


async def get_boj_dataset(name: str) -> dict[str, Any] | None:
    """Fetch a BOJ dataset."""
    if not _is_available("boj_mcp"):
        logger.debug("boj-mcp not installed, skipping")
        return None

    from boj_mcp.client import BojClient

    try:
        async with BojClient() as client:
            df = await client.get_dataset(name)
            info = client.get_dataframe_info(df, name)
            return {
                "source": "boj",
                "name": name,
                "shape": info.shape,
                "columns": info.columns,
                "date_range": info.date_range,
                "sample": df.tail(5).to_dicts(),
            }
    except Exception as e:
        logger.warning(f"BOJ fetch failed for {name}: {e}")
        return None


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------


def check_available_sources() -> dict[str, bool]:
    """Check which data sources are available."""
    sources = {
        "edinet": "edinet_mcp",
        "tdnet": "tdnet_disclosure_mcp",
        "estat": "estat_mcp",
        "boj": "boj_mcp",
        "stock": "yfinance_mcp",
    }
    return {name: _is_available(pkg) for name, pkg in sources.items()}


async def test_connections() -> dict[str, str]:
    """Test connectivity to all available sources."""
    results: dict[str, str] = {}
    available = check_available_sources()

    for source, is_available in available.items():
        if not is_available:
            results[source] = "not installed"
            continue

        try:
            if source == "edinet":
                companies = await search_companies_edinet("トヨタ")
                results[source] = f"ok ({len(companies)} results)"
            elif source == "tdnet":
                disclosures = await get_latest_disclosures(limit=1)
                results[source] = f"ok ({len(disclosures)} results)"
            elif source == "news":
                articles = await get_news(limit=1)
                results[source] = f"ok ({len(articles)} results)"
            elif source == "estat":
                tables = await get_estat_data("GDP", limit=1)
                results[source] = f"ok ({len(tables)} results)"
            elif source == "boj" or source == "stock":
                results[source] = "ok (installed)"
        except Exception as e:
            results[source] = f"error: {e}"

    return results
