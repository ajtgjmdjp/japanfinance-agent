"""Tests for japanfinance-agent CLI."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from japanfinance_agent.analysis import CompanyAnalysis, EarningsMonitor, MacroSnapshot
from japanfinance_agent.cli import cli


class TestCliHelp:
    """Test CLI help output."""

    def test_main_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Japan Finance Agent" in result.output

    def test_analyze_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "7203" in result.output

    def test_macro_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["macro", "--help"])
        assert result.exit_code == 0

    def test_monitor_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["monitor", "--help"])
        assert result.exit_code == 0

    def test_test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--help"])
        assert result.exit_code == 0

    def test_serve_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0


class TestCliAnalyze:
    """Test CLI analyze command."""

    @patch(
        "japanfinance_agent.analysis.analyze_company",
        new_callable=AsyncMock,
        return_value=CompanyAnalysis(
            code="7203",
            edinet_code="E02144",
            company_name="トヨタ自動車",
            statements=None,
            disclosures=[],
            news=[],
            stock_price=None,
            sources_used=["tdnet"],
        ),
    )
    def test_analyze_table_output(self, mock_analyze: AsyncMock) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "7203"])
        assert result.exit_code == 0
        assert "トヨタ自動車" in result.output

    @patch(
        "japanfinance_agent.analysis.analyze_company",
        new_callable=AsyncMock,
        return_value=CompanyAnalysis(
            code="7203",
            edinet_code=None,
            company_name=None,
            statements=None,
            disclosures=[],
            news=[],
            stock_price=None,
            sources_used=[],
        ),
    )
    def test_analyze_json_output(self, mock_analyze: AsyncMock) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "7203", "--json-output"])
        assert result.exit_code == 0
        assert '"code": "7203"' in result.output


class TestCliMonitor:
    """Test CLI monitor command."""

    @patch(
        "japanfinance_agent.analysis.earnings_monitor",
        new_callable=AsyncMock,
        return_value=EarningsMonitor(
            companies=[
                {
                    "code": "7203",
                    "company_name": "トヨタ",
                    "disclosures": [],
                    "metrics": None,
                },
            ],
            total_disclosures=0,
            sources_used=[],
        ),
    )
    def test_monitor_output(self, mock_monitor: AsyncMock) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["monitor", "7203"])
        assert result.exit_code == 0
        assert "Monitoring 1 companies" in result.output


class TestCliMacro:
    """Test CLI macro command."""

    @patch(
        "japanfinance_agent.analysis.macro_snapshot",
        new_callable=AsyncMock,
        return_value=MacroSnapshot(
            estat_data=[],
            sources_used=[],
        ),
    )
    def test_macro_output(self, mock_macro: AsyncMock) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["macro"])
        assert result.exit_code == 0
        assert "GDP" in result.output
