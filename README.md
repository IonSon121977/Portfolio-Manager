# 📊 Portfolio Intelligence Monitor

A fully automated personal portfolio monitoring system running on GitHub Actions with zero monthly cost. Tracks stocks and ETFs across all major European and US exchanges, sends email alerts, and provides a live dashboard.

**Dashboard:** https://ionson121977.github.io/Portfolio-Manager/

---

## 🏗 Architecture

```
GitHub Actions (5 workflows)
    ↓ fetch data via yfinance + FRED API
    ↓ commit JSON to docs/data/
GitHub Pages (static dashboard)
    ↓ serves docs/index.html + docs/data/*.json
Browser (password protected)
    ↓ renders dashboard from JSON files
```

**No server. No database. No paid APIs (except optional FRED + Anthropic keys). 100% free to host.**

---

## ⚡ Workflows

| Workflow | Schedule (CET) | What it does |
|---|---|---|
| **Price Digest** | 08:15 Mon–Fri | Morning digest email, snapshot, ETF holdings fetch, movement baseline, earnings alerts |
| **Movement & Intelligence** | 08:45, 11:00, 13:00, 15:45, 17:00 Mon–Fri | Price movement alerts (±3%), analyst ratings, consensus, news per holding |
| **Fundamentals Update** | Every 2h 08:00–18:00 Mon–Fri | Fundamentals, QVM scores, earnings surprise, revenue trends, sentiment, macro calendar |
| **Saturday Summary** | 09:00 Saturday | Weekly report email, top movers, next-week calendar, AI-written brief (Claude API) |
| **Deploy Pages** | On push to `docs/` | Publishes updated dashboard to GitHub Pages |

---

## 📁 Repository Structure

```
.github/workflows/
  price_digest.yml          # Morning digest + snapshot + ETF holdings + movement alerts
  movement_check.yml        # Intraday movement + intelligence (ratings + news)
  fundamentals.yml          # Fundamentals + QVM + sentiment + macro calendar
  saturday_summary.yml      # Weekly report + AI brief
  deploy.yml                # GitHub Pages deployment

scripts/
  shared.py                 # Core library: yfinance, FRED, iShares CSV, SSGA xlsx,
                            # news (multi-source), ratings, dividends, ETF holdings,
                            # email, FX conversion, sentiment indicators
  price_digest.py           # Morning digest + snapshot + movement alerts + 52W alerts
  intelligence.py           # Analyst ratings + consensus (6-month trend) + news
  fundamentals.py           # P/E, P/B, ROE, margins, growth, earnings surprise,
                            # revenue trends, analyst targets, short interest, GBX fix
  market_sentiment.py       # Composite sentiment: VSTOXX, VIX, EUR/USD, DAX, Stoxx50
  macro_calendar.py         # ECB/FOMC hardcoded + US CPI/NFP/Eurozone HICP via FRED
  saturday_summary.py       # Weekly report + AI brief via Anthropic API

docs/
  index.html                # Single-page dashboard (password protected, vanilla JS)
  data/
    snapshot.json           # Latest prices, EUR values, ETF top-25 holdings
    intelligence.json       # Analyst ratings, consensus, 6-month trend, news
    fundamentals.json       # Full fundamentals per holding
    market_sentiment.json   # Composite score + 5 market indicators
    weekly_report.json      # Next-week calendar + 4-week dividend calendar
    macro_calendar.json     # ECB/FOMC/CPI/NFP/HICP — rolling 4-week window
    alerts.json             # Alert log (last 500 entries)
    week_open.json          # Monday open prices for weekly change calculation
    52w_alerted_today.json  # 52W alert deduplication (resets daily)

portfolio_config.json       # Holdings config: tickers, shares, ISINs
requirements.txt            # Python deps — used by all 4 workflows
```

---

## 📈 Dashboard Tabs

### 🏠 Dashboard
- Total portfolio value in EUR with week-over-week change
- Per-holding table: live price, day change %, EUR value, analyst mean target, upside %, QVM score
- Reload button + last-updated timestamp

### 📊 Stock Scores (QVM)
- Quality-Value-Momentum composite score (0–100) per holding
- Quality inputs: ROE, profit margin, revenue growth, debt/equity, current ratio
- Value inputs: P/E, P/B, P/S, analyst upside vs mean target
- Momentum inputs: 52W range position, beta
- Sortable table, click-through score breakdown, export to CSV/JSON/XML/HTML/PDF

### 🌍 Market Intelligence
- **Composite Sentiment Score** (0–100): weighted average of VSTOXX, VIX, EUR/USD trend, Euro Stoxx 50 vs MA50, DAX vs MA50
- **Analyst Targets & 52W Range**: all holdings sorted by upside %, visual 52W bar, consensus grade
- **Short Interest**: short % of float + days-to-cover ranked table with squeeze risk indicator
- **Earnings Surprise History**: last 4 quarters beat/miss per holding, streak badge (✓✓✓✗), portfolio beat rate
- **Revenue vs Net Income trend**: 4-quarter bar chart per holding
- **Insider Transactions**: last 10 transactions per holding

### 🧠 Intelligence
- **Rating changes table**: last 7 days across all US holdings (yfinance upgrades_downgrades)
- **Per-holding cards** showing:
  - Consensus badge: Buy/Hold/Sell counts, total analyst count, trend arrow (improving/deteriorating/stable) — works for all exchanges via `t.recommendations`
  - 6-month consensus trend sparkline (stacked Buy/Hold/Sell bars, hoverable)
  - 30-day broker change timeline: colour-coded dots (🟢 upgrade / 🔴 downgrade / ⚪ reiteration), hover for firm + grade detail
  - News: up to 6 articles from yfinance, Google News RSS, Bing News RSS, Seeking Alpha (US only), deduplicated by title, sorted by date

### 🗂 ETF Holdings
- Top 25 holdings per ETF with proportional weight % bar
- **EUNK, IS3N, QDVE, SEMI**: fetched from iShares/BlackRock CSV endpoint (full holdings file)
- **SPYY**: fetched from SSGA daily xlsx (columns: ISIN, Security Name, Percent of Fund)
- Falls back to yfinance `funds_data.top_holdings` (10 holdings) if provider fetch fails

### 🔔 Alerts
- Filterable log of all alerts: movement, rating change, 52W high/low, earnings proximity, digest
- Last 500 entries with timestamp, ticker, type, message

### 📅 Weekly Report
- **Sentiment banner**: composite score + emoji, VIX level (colour-coded), VSTOXX level
- **Analyst Targets table**: all holdings sorted by analyst upside, with 52W range bar and consensus grade
- **Earnings Calls**: next week — date, ticker, company, quarter, EPS estimate, revenue estimate
- **Ex-Dividend Calendar**: rolling 4-week forward view — ex-date, ticker, company, amount (€/£/$), currency, pay date; grouped by week
- **Stock Splits**: next week
- **Macro Event Calendar**: ECB decision + press conference, FOMC, US CPI, US NFP, Eurozone HICP — next 4 weeks, filterable by All / High Impact / EUR / USD / GBP

### ⚙ Configure
- Add/remove stocks and ETFs via form UI
- Set password, alert thresholds
- Download updated `portfolio_config.json`

---

## 📧 Email Alerts

All emails sent via SMTP (any provider — Gmail, Outlook etc.)

| Alert | Trigger |
|---|---|
| Morning Digest | Daily 08:15 CET — snapshot + top movers + news headlines |
| Movement Alert | Holding moves ±3% from morning baseline (checked 5× per day) |
| Rating Change | New broker upgrade/downgrade detected today (US stocks, yfinance) |
| 52W High/Low | Holding within 0.5% of 52-week high or low — once per day per ticker |
| Earnings Alert | Holding reports earnings within 2 trading days |
| Weekly Summary | Saturday ~09:30 CET — movers, next-week calendar, AI-written brief |

---

## 🔐 Security

- Dashboard protected by client-side password stored in `sessionStorage`
- All API keys and credentials stored as GitHub Secrets — never committed to the repo
- `portfolio_config.json` contains no secrets (tickers, shares, ISINs only)

---

## 💹 Portfolio Holdings

### Stocks (34 active + 3 price-only)

| Ticker | Name | Exchange |
|---|---|---|
| MSFT | Microsoft | NASDAQ |
| GOOG | Alphabet (Google) Class C | NASDAQ |
| NVDA | NVIDIA | NASDAQ |
| AMZN | Amazon | NASDAQ |
| AAPL | Apple | NASDAQ |
| LLY | Eli Lilly | NYSE |
| CAT | Caterpillar | NYSE |
| GE | GE Aerospace | NYSE |
| XOM | Exxon Mobil | NYSE |
| CVX | Chevron | NYSE |
| MU | Micron Technology | NASDAQ |
| INTC | Intel | NASDAQ |
| AMD | Advanced Micro Devices | NASDAQ |
| TXN | Texas Instruments | NASDAQ |
| ASML | ASML Holding | NASDAQ |
| ENR.DE | Siemens Energy | XETRA |
| VH2.DE | Friedrich Vorwerk Group | XETRA |
| GBF.DE | Bilfinger | XETRA |
| SMHN.DE | SÜSS MicroTec | XETRA |
| ALV.DE | Allianz SE | XETRA |
| AIR.PA | Airbus | Euronext Paris |
| HO.PA | Thales | Euronext Paris |
| TTE.PA | TotalEnergies | Euronext Paris |
| STM.PA | STMicroelectronics | Euronext Paris |
| SU.PA | Schneider Electric | Euronext Paris |
| BESI.AS | BE Semiconductor (BESI) | Euronext Amsterdam |
| ASM.AS | ASM International (ASMI) | Euronext Amsterdam |
| BA.L | BAE Systems | LSE |
| SHEL.L | Shell | LSE |
| BP.L | BP | LSE |
| MILDEF.ST | MilDef Group | Nasdaq Stockholm |
| IBE.MC | Iberdrola | BME Madrid |
| REP.MC | Repsol | BME Madrid |
| SNDK | SanDisk | NASDAQ |
| BTC-USD | Bitcoin | — |
| GC=F | Gold (Futures) | — |
| SI=F | Silver (Futures) | — |

> BTC-USD, GC=F, SI=F are price-only — no fundamentals, no ratings, no news.
> SNDK is skipped in earnings calendar (returns incorrect data from Yahoo).

### ETFs (5)

| Ticker | Name | Exchange | Holdings Source |
|---|---|---|---|
| SPYY.DE | SPDR MSCI ACWI UCITS ETF | XETRA | SSGA xlsx |
| EUNK.DE | iShares Core MSCI Europe UCITS ETF | XETRA | iShares CSV |
| QDVE.DE | iShares S&P 500 IT Sector UCITS ETF | XETRA | iShares CSV |
| IS3N.DE | iShares Core MSCI EM IMI UCITS ETF | XETRA | iShares CSV |
| SEMI.AS | iShares MSCI Global Semiconductors UCITS ETF | Euronext Amsterdam | iShares CSV |

---

## 🛠 Tech Stack

| Component | Technology |
|---|---|
| Prices, fundamentals, news, ratings | yfinance (free, no key) |
| ETF holdings — iShares products | iShares/BlackRock CSV endpoint (free, no key) |
| ETF holdings — SPDR products | SSGA daily xlsx (free, no key) |
| Macro event dates (CPI, NFP, HICP) | FRED API (free key — fred.stlouisfed.org) |
| AI weekly brief | Anthropic Claude API (claude-sonnet, pay-per-use) |
| Email delivery | SMTP (any provider) |
| Hosting | GitHub Pages (free) |
| CI/CD | GitHub Actions (free tier, ~300 min/month used) |
| Language | Python 3.11 + vanilla HTML/JS/CSS (no frameworks) |
| Python dependencies | `yfinance`, `requests`, `lxml`, `openpyxl`, `mstarpy`, `anthropic` |

---

## ⚙ GitHub Secrets Required

| Secret | Required | Used by | Description |
|---|---|---|---|
| `EMAIL_FROM` | ✅ | All | SMTP sender address |
| `EMAIL_PASSWORD` | ✅ | All | SMTP app password |
| `EMAIL_TO` | ✅ | All | Recipient email address |
| `ANTHROPIC_API_KEY` | Optional | Saturday summary | Claude API key — for AI weekly brief |
| `FRED_API_KEY` | Optional | Fundamentals | FRED key — for CPI/NFP/HICP release dates |

---

## 📅 Summer / Winter Time Note

Cron schedules are in UTC. Austria (CET = UTC+1, CEST = UTC+2):

- **Winter (CET)**: UTC cron = local time − 1h (e.g. `07:15 UTC` = `08:15 CET`)
- **Summer (CEST)**: UTC cron = local time − 2h (e.g. `06:15 UTC` = `08:15 CEST`)

The workflows are currently set for **CET (winter)**. Adjust all cron lines by −1h in late March when CEST begins, and revert in late October.
