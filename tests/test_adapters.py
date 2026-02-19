"""Tests for japanfinance-agent adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from japanfinance_agent import adapters


class TestIsAvailable:
    """Test _is_available helper."""

    def test_available_package(self) -> None:
        assert adapters._is_available("json") is True

    def test_unavailable_package(self) -> None:
        assert adapters._is_available("nonexistent_package_xyz") is False


class TestCheckAvailableSources:
    """Test check_available_sources."""

    def test_returns_dict(self) -> None:
        result = adapters.check_available_sources()
        assert isinstance(result, dict)
        assert "edinet" in result
        assert "tdnet" in result
        assert "estat" in result
        assert "boj" in result
        assert "stock" in result

    def test_all_bool_values(self) -> None:
        result = adapters.check_available_sources()
        for value in result.values():
            assert isinstance(value, bool)


class TestEdinetAdapter:
    """Test EDINET adapter functions."""

    @patch.object(adapters, "_is_available", return_value=False)
    async def test_get_company_statements_not_installed(
        self,
        mock_avail: MagicMock,
    ) -> None:
        result = await adapters.get_company_statements("E02144")
        assert result is None

    @patch.object(adapters, "_is_available", return_value=False)
    async def test_search_companies_not_installed(
        self,
        mock_avail: MagicMock,
    ) -> None:
        result = await adapters.search_companies_edinet("トヨタ")
        assert result == []

    @patch.object(adapters, "_is_available", return_value=True)
    async def test_get_company_statements_error_handling(
        self,
        mock_avail: MagicMock,
    ) -> None:
        mock_module = MagicMock()
        mock_module.EdinetClient.side_effect = Exception("test error")
        with patch.dict("sys.modules", {"edinet_mcp": mock_module}):
            result = await adapters.get_company_statements("E02144")
            assert result is None


class TestTdnetAdapter:
    """Test TDNET adapter functions."""

    @patch.object(adapters, "_is_available", return_value=False)
    async def test_get_company_disclosures_not_installed(
        self,
        mock_avail: MagicMock,
    ) -> None:
        result = await adapters.get_company_disclosures("7203")
        assert result == []

    @patch.object(adapters, "_is_available", return_value=False)
    async def test_get_latest_not_installed(
        self,
        mock_avail: MagicMock,
    ) -> None:
        result = await adapters.get_latest_disclosures()
        assert result == []


class TestNewsAdapter:
    """Test news adapter functions."""

    @patch.object(adapters, "_is_available", return_value=False)
    async def test_get_news_not_installed(
        self,
        mock_avail: MagicMock,
    ) -> None:
        result = await adapters.get_news("トヨタ")
        assert result == []


class TestStockPriceAdapter:
    """Test stock price adapter functions."""

    @patch.object(adapters, "_is_available", return_value=False)
    async def test_get_stock_price_not_installed(
        self,
        mock_avail: MagicMock,
    ) -> None:
        result = await adapters.get_stock_price("7203")
        assert result is None


class TestEstatAdapter:
    """Test e-Stat adapter functions."""

    @patch.object(adapters, "_is_available", return_value=False)
    async def test_get_estat_data_not_installed(
        self,
        mock_avail: MagicMock,
    ) -> None:
        result = await adapters.get_estat_data("GDP")
        assert result == []


class TestBojAdapter:
    """Test BOJ adapter functions."""

    @patch.object(adapters, "_is_available", return_value=False)
    async def test_get_boj_dataset_not_installed(
        self,
        mock_avail: MagicMock,
    ) -> None:
        result = await adapters.get_boj_dataset("rates")
        assert result is None


class TestTestConnections:
    """Test the connectivity check."""

    @patch.object(adapters, "check_available_sources")
    async def test_all_not_installed(
        self,
        mock_check: MagicMock,
    ) -> None:
        mock_check.return_value = {
            "edinet": False,
            "tdnet": False,
            "estat": False,
            "boj": False,
            "stock": False,
        }
        results = await adapters.test_connections()
        assert all(v == "not installed" for v in results.values())
