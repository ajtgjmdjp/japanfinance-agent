"""Command-line interface for japanfinance-agent."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from typing import Literal, cast

import click
from loguru import logger

_CODE_RE = re.compile(r"^\d{4}$")


def _validate_code(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """Validate a 4-digit stock code."""
    if not _CODE_RE.match(value):
        raise click.BadParameter(f"{value!r} is not a valid 4-digit stock code")
    return value


def _validate_codes(
    ctx: click.Context, param: click.Parameter, value: tuple[str, ...]
) -> tuple[str, ...]:
    """Validate a tuple of stock codes."""
    if len(value) > 20:
        raise click.BadParameter(f"Too many codes ({len(value)}, max 20)")
    for v in value:
        if not _CODE_RE.match(v):
            raise click.BadParameter(f"{v!r} is not a valid 4-digit stock code")
    return value


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool) -> None:
    """Japan Finance Agent — compound analysis from 6 data sources."""
    level = "DEBUG" if verbose else "INFO"
    logger.remove()
    logger.add(sys.stderr, level=level, format="{time:HH:mm:ss} | {level:<7} | {message}")


@cli.command()
@click.argument("code", callback=_validate_code)
@click.option("--edinet-code", "-e", default=None, help="EDINET code (e.g. E02144).")
@click.option("--period", "-p", default=None, help="Filing year (e.g. 2025).")
@click.option("--json-output", "-j", "as_json", is_flag=True, help="Output as JSON.")
def analyze(code: str, edinet_code: str | None, period: str | None, as_json: bool) -> None:
    """Analyze a company (EDINET + TDNET + news + stock).

    Examples:

        japanfinance-agent analyze 7203

        japanfinance-agent analyze 7203 -e E02144 -p 2025 --json-output
    """
    from japanfinance_agent.analysis import analyze_company

    result = asyncio.run(analyze_company(code, edinet_code=edinet_code, period=period))

    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    click.echo(f"Company: {result['company_name'] or code}")
    click.echo(f"Sources: {', '.join(result['sources_used']) or 'none'}\n")

    if result["statements"]:
        metrics = result["statements"].get("metrics", {})
        click.echo("--- Financial Metrics ---")
        for category in ("profitability", "stability", "efficiency", "growth"):
            cat_data = metrics.get(category, {})
            if cat_data:
                for key, val in cat_data.items():
                    click.echo(f"  {key}: {val}")
        click.echo()

    if result["disclosures"]:
        click.echo(f"--- Recent Disclosures ({len(result['disclosures'])}) ---")
        for d in result["disclosures"][:5]:
            click.echo(f"  [{d['category']}] {d['title']}")
            click.echo(f"    {d['pubdate']}")
        click.echo()

    if result["stock_price"]:
        sp = result["stock_price"]
        click.echo("--- Stock Price ---")
        click.echo(f"  Date: {sp['date']}, Close: {sp['close']}")
        click.echo()

    if result["news"]:
        click.echo(f"--- News ({len(result['news'])}) ---")
        for n in result["news"][:3]:
            click.echo(f"  {n['title']}")
            click.echo(f"    {n.get('source_name', '')} {n.get('published', '')}")


@cli.command()
@click.option("--keyword", "-k", default="GDP", help="e-Stat search keyword.")
@click.option("--boj-dataset", "-b", default=None, help="BOJ dataset name.")
@click.option("--json-output", "-j", "as_json", is_flag=True, help="Output as JSON.")
def macro(keyword: str, boj_dataset: str | None, as_json: bool) -> None:
    """Macro economic snapshot (e-Stat + BOJ + news).

    Examples:

        japanfinance-agent macro

        japanfinance-agent macro -k CPI --json-output
    """
    from japanfinance_agent.analysis import macro_snapshot

    result = asyncio.run(macro_snapshot(keyword=keyword, boj_dataset=boj_dataset))

    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    click.echo(f"Keyword: {keyword}")
    click.echo(f"Sources: {', '.join(result['sources_used']) or 'none'}\n")

    if result["estat_data"]:
        click.echo(f"--- e-Stat ({len(result['estat_data'])} tables) ---")
        for t in result["estat_data"]:
            click.echo(f"  [{t['stats_id']}] {t['title']}")
        click.echo()

    if result["news"]:
        click.echo(f"--- News ({len(result['news'])}) ---")
        for n in result["news"][:5]:
            click.echo(f"  {n['title']}")


@cli.command()
@click.argument("codes", nargs=-1, required=True, callback=_validate_codes)
@click.option("--json-output", "-j", "as_json", is_flag=True, help="Output as JSON.")
def monitor(codes: tuple[str, ...], as_json: bool) -> None:
    """Monitor earnings for a watchlist (TDNET disclosures).

    Examples:

        japanfinance-agent monitor 7203 6758 6861

        japanfinance-agent monitor 7203 6758 --json-output
    """
    from japanfinance_agent.analysis import earnings_monitor

    result = asyncio.run(earnings_monitor(list(codes)))

    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    click.echo(f"Monitoring {len(codes)} companies")
    click.echo(f"Total disclosures: {result['total_disclosures']}\n")

    for entry in result["companies"]:
        name = entry["company_name"] or entry["code"]
        click.echo(f"--- {name} ({entry['code']}) ---")
        if entry["disclosures"]:
            for d in entry["disclosures"][:3]:
                click.echo(f"  [{d['category']}] {d['title']}")
        else:
            click.echo("  No recent disclosures")
        click.echo()


@cli.command("test")
def test_connection() -> None:
    """Test connectivity to all data sources.

    Checks which Japan finance MCP packages are installed and working.

    Examples:

        japanfinance-agent test
    """
    from japanfinance_agent import __version__, adapters

    click.echo(f"japanfinance-agent v{__version__}\n")

    # Check availability
    available = adapters.check_available_sources()
    click.echo("Data source availability:")
    for source, is_available in available.items():
        status = "[OK]  " if is_available else "[MISS]"
        click.echo(f"  {status} {source}")

    click.echo("\nTesting connections...")
    results = asyncio.run(adapters.test_connections())
    for source, status in results.items():
        icon = "[OK]  " if status.startswith("ok") else "[FAIL]"
        click.echo(f"  {icon} {source}: {status}")


@cli.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="MCP transport protocol.",
)
def serve(transport: str) -> None:
    """Start the Japan Finance Agent MCP server.

    For Claude Desktop, add to config::

        {"mcpServers": {"japanfinance":
          {"command": "uvx", "args": ["japanfinance-agent", "serve"]}}}
    """
    from japanfinance_agent.server import mcp

    logger.info(f"Starting Japan Finance Agent MCP server ({transport} transport)")
    mcp.run(transport=cast('Literal["stdio", "sse"]', transport))
