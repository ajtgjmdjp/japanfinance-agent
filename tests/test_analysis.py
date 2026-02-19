"""Tests for japanfinance-agent analysis tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from japanfinance_agent import adapters
from japanfinance_agent.analysis import (
    analyze_company,
    earnings_monitor,
    macro_snapshot,
)


class TestAnalyzeCompany:
    """Test analyze_company compound tool."""

    @patch.object(adapters, "get_stock_price", new_callable=AsyncMock, return_value=None)
    @patch.object(
        adapters,
        "get_company_disclosures",
        new_callable=AsyncMock,
        return_value=[
            {
                "source": "tdnet",
                "pubdate": "2026-02-14",
                "company_name": "トヨタ自動車",
                "title": "決算短信",
                "category": "earnings",
                "document_url": "https://example.com/doc.pdf",
            },
        ],
    )
    @patch.object(
        adapters,
        "get_company_statements",
        new_callable=AsyncMock,
        return_value={
            "source": "edinet",
            "company_name": "トヨタ自動車株式会社",
            "edinet_code": "E02144",
            "accounting_standard": "IFRS",
            "metrics": {"profitability": {"ROE": "12.5%"}},
        },
    )
    @patch.object(
        adapters,
        "search_companies_edinet",
        new_callable=AsyncMock,
        return_value=[
            {"edinet_code": "E02144", "name": "トヨタ自動車株式会社", "ticker": "7203"},
        ],
    )
    async def test_full_analysis(
        self,
        mock_search: AsyncMock,
        mock_stmt: AsyncMock,
        mock_disc: AsyncMock,
        mock_stock: AsyncMock,
    ) -> None:
        result = await analyze_company("7203")

        assert result["code"] == "7203"
        assert result["edinet_code"] == "E02144"
        assert result["company_name"] is not None
        assert "edinet" in result["sources_used"]
        assert "tdnet" in result["sources_used"]
        assert result["statements"] is not None
        assert len(result["disclosures"]) == 1

    @patch.object(adapters, "get_stock_price", new_callable=AsyncMock, return_value=None)
    @patch.object(
        adapters,
        "get_company_disclosures",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch.object(
        adapters,
        "search_companies_edinet",
        new_callable=AsyncMock,
        return_value=[],
    )
    async def test_no_sources_available(
        self,
        mock_search: AsyncMock,
        mock_disc: AsyncMock,
        mock_stock: AsyncMock,
    ) -> None:
        result = await analyze_company("9999")

        assert result["code"] == "9999"
        assert result["edinet_code"] is None
        assert result["statements"] is None
        assert result["sources_used"] == []

    @patch.object(adapters, "get_stock_price", new_callable=AsyncMock, return_value=None)
    @patch.object(
        adapters,
        "get_company_disclosures",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch.object(
        adapters,
        "get_company_statements",
        new_callable=AsyncMock,
        return_value={"source": "edinet", "company_name": "Test Co"},
    )
    async def test_with_edinet_code_provided(
        self,
        mock_stmt: AsyncMock,
        mock_disc: AsyncMock,
        mock_stock: AsyncMock,
    ) -> None:
        result = await analyze_company("7203", edinet_code="E02144")

        assert result["edinet_code"] == "E02144"
        mock_stmt.assert_called_once()

    @patch.object(
        adapters,
        "get_stock_price",
        new_callable=AsyncMock,
        side_effect=Exception("API error"),
    )
    @patch.object(
        adapters,
        "get_company_disclosures",
        new_callable=AsyncMock,
        side_effect=Exception("TDNET error"),
    )
    @patch.object(
        adapters,
        "search_companies_edinet",
        new_callable=AsyncMock,
        return_value=[],
    )
    async def test_handles_all_errors_gracefully(
        self,
        mock_search: AsyncMock,
        mock_disc: AsyncMock,
        mock_stock: AsyncMock,
    ) -> None:
        result = await analyze_company("7203")

        assert result["code"] == "7203"
        assert result["sources_used"] == []


class TestMacroSnapshot:
    """Test macro_snapshot compound tool."""

    @patch.object(
        adapters,
        "get_estat_data",
        new_callable=AsyncMock,
        return_value=[{"source": "estat", "stats_id": "001", "title": "GDP"}],
    )
    async def test_macro_with_estat(
        self,
        mock_estat: AsyncMock,
    ) -> None:
        result = await macro_snapshot(keyword="GDP")

        assert "estat" in result["sources_used"]
        assert len(result["estat_data"]) == 1

    @patch.object(adapters, "get_estat_data", new_callable=AsyncMock, return_value=[])
    async def test_macro_no_data(
        self,
        mock_estat: AsyncMock,
    ) -> None:
        result = await macro_snapshot()

        assert result["sources_used"] == []
        assert result["estat_data"] == []


class TestEarningsMonitor:
    """Test earnings_monitor compound tool."""

    @patch.object(
        adapters,
        "get_company_disclosures",
        new_callable=AsyncMock,
        return_value=[
            {
                "source": "tdnet",
                "pubdate": "2026-02-14",
                "company_name": "トヨタ自動車",
                "title": "決算短信",
                "category": "earnings",
            },
        ],
    )
    async def test_single_company(self, mock_disc: AsyncMock) -> None:
        result = await earnings_monitor(["7203"])

        assert len(result["companies"]) == 1
        assert result["total_disclosures"] == 1
        assert "tdnet" in result["sources_used"]
        assert result["companies"][0]["code"] == "7203"
        assert result["companies"][0]["company_name"] == "トヨタ自動車"

    @patch.object(
        adapters,
        "get_company_disclosures",
        new_callable=AsyncMock,
        return_value=[],
    )
    async def test_no_disclosures(self, mock_disc: AsyncMock) -> None:
        result = await earnings_monitor(["9999"])

        assert result["total_disclosures"] == 0
        assert result["companies"][0]["company_name"] is None

    @patch.object(
        adapters,
        "get_company_disclosures",
        new_callable=AsyncMock,
        side_effect=Exception("API error"),
    )
    async def test_error_handling(self, mock_disc: AsyncMock) -> None:
        result = await earnings_monitor(["7203"])

        assert len(result["companies"]) == 1
        assert result["total_disclosures"] == 0
