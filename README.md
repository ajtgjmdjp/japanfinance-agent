# japanfinance-agent

[![CI](https://github.com/ajtgjmdjp/japanfinance-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/ajtgjmdjp/japanfinance-agent/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/japanfinance-agent.svg)](https://pypi.org/project/japanfinance-agent/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Compound [MCP](https://modelcontextprotocol.io/) agent that combines **6 Japan finance data sources** into high-value analysis tools. Instead of calling each source individually, get comprehensive company analysis, macro snapshots, and earnings monitoring in a single request.

Part of the [Japan Finance Data Stack](https://github.com/ajtgjmdjp/awesome-japan-finance-data): [edinet-mcp](https://github.com/ajtgjmdjp/edinet-mcp) (securities filings) | [tdnet-disclosure-mcp](https://github.com/ajtgjmdjp/tdnet-disclosure-mcp) (timely disclosures) | [estat-mcp](https://github.com/ajtgjmdjp/estat-mcp) (government statistics) | [boj-mcp](https://github.com/ajtgjmdjp/boj-mcp) (Bank of Japan) | [japan-news-mcp](https://github.com/ajtgjmdjp/japan-news-mcp) (financial news) | [stockprice-mcp](https://github.com/ajtgjmdjp/stockprice-mcp) (stock prices)

## Why?

Each Japan finance MCP provides focused data from one source. But real analysis needs multiple sources combined:

| What you want | Without japanfinance-agent | With japanfinance-agent |
|---|---|---|
| Company analysis | 4 sequential MCP calls (EDINET → TDNET → news → stock) | `analyze 7203` |
| Macro overview | 3 sequential MCP calls (e-Stat → BOJ → news) | `macro -k GDP` |
| Earnings watchlist | N × TDNET calls for N companies | `monitor 7203 6758 6861` |

## Installation

```bash
# Core only (brings no data sources)
pip install japanfinance-agent

# With all data sources
pip install "japanfinance-agent[all]"

# Pick specific sources
pip install "japanfinance-agent[edinet,tdnet,news]"
```

Available extras: `edinet`, `tdnet`, `estat`, `boj`, `news`, `stock`, `all`

## Configuration

Add to Claude Desktop config:

```json
{
  "mcpServers": {
    "japanfinance": {
      "command": "uvx",
      "args": ["japanfinance-agent[all]", "serve"],
      "env": {
        "EDINET_API_KEY": "your_edinet_key",
        "ESTAT_APP_ID": "your_estat_app_id"
      }
    }
  }
}
```

Then ask: "トヨタの財務分析をして" or "日本のGDP関連の最新データを見せて"

## MCP Tools

| Tool | Description |
|------|-------------|
| `analyze_japanese_company` | 企業の包括分析（EDINET財務 + TDNET開示 + ニュース + 株価） |
| `get_macro_snapshot` | マクロ経済スナップショット（e-Stat + BOJ + ニュース） |
| `monitor_earnings` | 複数企業の決算・開示モニタリング |
| `check_data_sources` | データソースの接続状況を確認 |

## CLI Usage

```bash
# Analyze a company (EDINET + TDNET + news + stock)
japanfinance-agent analyze 7203
japanfinance-agent analyze 7203 -e E02144 -p 2025 --json-output

# Macro economic snapshot (e-Stat + BOJ + news)
japanfinance-agent macro
japanfinance-agent macro -k CPI

# Monitor earnings for a watchlist
japanfinance-agent monitor 7203 6758 6861

# Check which data sources are available
japanfinance-agent test

# Start MCP server
japanfinance-agent serve
```

## Architecture

```
japanfinance-agent
├── analyze_company(code)     → EDINET + TDNET + news + stock (parallel)
├── macro_snapshot(keyword)   → e-Stat + BOJ + news (parallel)
├── earnings_monitor(codes[]) → TDNET × N companies (parallel)
└── check_data_sources()      → connectivity status

Adapters (graceful degradation — missing packages return empty results):
├── edinet-mcp    → Financial statements, metrics, company search
├── tdnet-mcp     → Timely disclosures (earnings, dividends, buybacks)
├── estat-mcp     → Government statistics (GDP, CPI, employment)
├── boj-mcp       → Bank of Japan data (rates, money supply)
├── japan-news-mcp → Financial news headlines
└── stockprice-mcp → Stock prices & FX (via yfinance)
```

## Data Sources

| Source | Auth | Data |
|---|---|---|
| [EDINET](https://disclosure.edinet-fsa.go.jp/) | API key (free) | Securities filings, XBRL financial statements |
| [TDNET](https://www.release.tdnet.info/) | None | Timely disclosures (earnings, dividends) |
| [e-Stat](https://www.e-stat.go.jp/) | App ID (free) | Government statistics (GDP, CPI, employment) |
| [BOJ](https://www.stat-search.boj.or.jp/) | None | Central bank data (rates, money supply) |
| [News](https://news.yahoo.co.jp/categories/business) | None | RSS feeds (Yahoo, NHK, Reuters, Toyo Keizai) |

## License

Apache-2.0
