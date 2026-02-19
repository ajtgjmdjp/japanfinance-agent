"""japanfinance-agent: Compound MCP agent for Japan finance data.

Combines 6 data sources — EDINET (securities filings), TDNET (disclosures),
e-Stat (government statistics), BOJ (central bank), news, and stock prices —
into high-value compound analysis tools.
"""

from japanfinance_agent.analysis import (
    CompanyAnalysis,
    EarningsEntry,
    EarningsMonitor,
    MacroSnapshot,
    analyze_company,
    earnings_monitor,
    macro_snapshot,
)

__all__ = [
    "CompanyAnalysis",
    "EarningsEntry",
    "EarningsMonitor",
    "MacroSnapshot",
    "analyze_company",
    "earnings_monitor",
    "macro_snapshot",
]

__version__ = "0.1.4"
