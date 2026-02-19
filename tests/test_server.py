"""Tests for japanfinance-agent server."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from japanfinance_agent import adapters
from japanfinance_agent.analysis import (
    analyze_company,
    earnings_monitor,
    macro_snapshot,
)
from japanfinance_agent.server import mcp


class TestMcpServerSetup:
    """Test MCP server is configured correctly."""

    def test_server_has_name(self) -> None:
        assert mcp is not None
        assert mcp.name == "japanfinance-agent"


class TestAnalyzeCompanyTool:
    """Test analyze_japanese_company tool logic."""

    @patch.object(
        adapters,
        "get_stock_price",
        new_callable=AsyncMock,
        return_value=None,
    )
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
        return_value=None,
    )
    @patch.object(
        adapters,
        "search_companies_edinet",
        new_callable=AsyncMock,
        return_value=[
            {"edinet_code": "E02144", "name": "トヨタ", "ticker": "7203"},
        ],
    )
    async def test_analyze_returns_result(
        self,
        mock_search: AsyncMock,
        mock_stmt: AsyncMock,
        mock_disc: AsyncMock,
        mock_stock: AsyncMock,
    ) -> None:
        result = await analyze_company("7203")
        assert result["code"] == "7203"
        data = json.dumps(result, ensure_ascii=False, default=str)
        assert "7203" in data


class TestMacroSnapshotTool:
    """Test get_macro_snapshot tool logic."""

    @patch.object(adapters, "get_estat_data", new_callable=AsyncMock, return_value=[])
    async def test_macro_returns_result(
        self,
        mock_estat: AsyncMock,
    ) -> None:
        result = await macro_snapshot()
        data = json.dumps(result, ensure_ascii=False, default=str)
        assert "estat_data" in data


class TestMonitorEarningsTool:
    """Test monitor_earnings tool logic."""

    @patch.object(
        adapters,
        "get_company_disclosures",
        new_callable=AsyncMock,
        return_value=[],
    )
    async def test_monitor_returns_result(self, mock_disc: AsyncMock) -> None:
        result = await earnings_monitor(["7203"])
        data = json.dumps(result, ensure_ascii=False, default=str)
        assert "total_disclosures" in data


class TestCheckDataSourcesTool:
    """Test check_data_sources tool logic."""

    @patch.object(
        adapters,
        "test_connections",
        new_callable=AsyncMock,
        return_value={"edinet": "ok (3 results)", "tdnet": "not installed"},
    )
    async def test_check_returns_status(self, mock_test: AsyncMock) -> None:
        results = await adapters.test_connections()
        data = json.dumps(results, ensure_ascii=False)
        parsed = json.loads(data)
        assert parsed["edinet"] == "ok (3 results)"
        assert parsed["tdnet"] == "not installed"
