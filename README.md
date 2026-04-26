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

**No server. No database. No paid APIs (except optional FRED key for macro calendar). 100% free.**

---

## ⚡ Workflows

| Workflow | Schedule (CET) | What it does |
|---|---|---|
| **Price Digest** | 08:15 Mon–Fri | Morning digest email, snapshot, price baseline, ETF holdings, earnings alerts |
| **Movement & Intelligence** | 08:45, 11:00, 13:00, 15:45, 17:00 Mon–Fri | Price movement alerts (±3%), analyst ratings, news fetch, consensus data |
| **Fundamentals Update** | Every 2h 08:00–18:00 Mon–Fri | Fundamentals, QVM scores, earnings surprise, revenue trends, sentiment, macro calendar |
| **Saturday Summary** | 09:00 Saturday | Weekly summary email, top movers, next week calendar, AI-written weekly brief |
| **Deploy Pages** | On push to `docs/` | Publishes updated dashboard to GitHub Pages |

---

## 📁 Repository Structure

```
.github/workflows/
  price_digest.yml          # Morning digest + movement + ETF holdings
  movement_check.yml        # Intraday movement + intelligence checks
  fundamentals.yml          # Fundamentals + sentiment + macro calendar
  saturday_summary.yml      # Weekly report + AI brief
  deploy.yml                # GitHub Pages deployment

scripts/
  shared.py                 # All data fetching: yfinance, FRED, news, ratings,
                            # dividends, ETF holdings, email, FX conversion
  price_digest.py           # Morning digest + snapshot + movement alerts + 52W alerts
  intelligence.py           # Analyst ratings + consensus + news (per holding)
  fundamentals.py           # P/E, P/B, ROE, margins, growth, earnings surprise,
                            # revenue trends, analyst targets, short interest
  market_sentiment.py       # Composite sentiment (VSTOXX, VIX, EUR/USD, DAX, Stoxx50)
  macro_calendar.py         # ECB/FOMC (hardcoded) + CPI/NFP/HICP via FRED API
  saturday_summary.py       # Weekly report + AI brief (Anthropic API)

docs/
  index.html                # Single-page dashboard (password protected)
  data/
    snapshot.json           # Latest prices, values, ETF holdings
    intelligence.json       # Analyst ratings, consensus, news per holding
    fundamentals.json       # Full fundamentals per holding
    market_sentiment.json   # Composite score + 5 market indicators
    weekly_report.json      # Weekly calendar + AI brief
    macro_calendar.json     # ECB/FOMC/CPI/NFP/HICP events (4-week window)
    alerts.json             # Alert log (last 500)
    week_open.json          # Monday open prices for weekly change calculation
    52w_alerted_today.json  # 52W alert deduplication (resets daily)

portfolio_config.json       # Holdings: tickers, shares, ISINs, Finnhub symbols
requirements.txt            # Python dependencies (all workflows use this)
```

---

## 📈 Dashboard Tabs

### 🏠 Dashboard
- Total portfolio value in EUR with week-over-week change
- Stocks and ETFs table: live price, day change %, EUR value, analyst target, QVM score
- Last updated timestamp with reload button

### 📊 Stock Scores (QVM)
- Quality-Value-Momentum score (0–100) per holding
- Inputs: P/E, P/B, P/S, ROE, profit margin, revenue growth, debt/equity, current ratio, 52W range, analyst upside, beta
- Sortable table with click-through score breakdown
- Export to CSV, JSON, XML, HTML, PDF

### 🌍 Market Intelligence
- **Composite Sentiment Score** (0–100): VSTOXX, VIX, EUR/USD, Euro Stoxx 50 vs MA50, DAX vs MA50
- **Analyst Targets & 52W Range**: consensus target, upside %, visual range bar per holding
- **Short Interest**: short % of float, days-to-cover, ranked table
- **Earnings Surprise History**: last 4 quarters beat/miss with streak indicator (✓✓✓✗), portfolio beat rate
- **Revenue vs Net Income trend**: last 4 quarters per holding
- **Insider Transactions**: last 10 per holding

### 🧠 Intelligence
- **Analyst rating changes** (last 7 days) — US stocks via yfinance; European stocks via monthly consensus
- **Consensus badge per holding**: Buy/Hold/Sell counts, analyst count, trend (improving/deteriorating/stable)
- **6-month consensus trend chart**: stacked bar (Buy/Hold/Sell) per month
- **30-day broker change timeline**: colour-coded dots (green=upgrade, red=downgrade, grey=reiteration)
- **News by holding**: up to 6 articles from yfinance, Google News, Bing News, Seeking Alpha (US only)

### 🗂 ETF Holdings
- Top 15 holdings per ETF with weight % bar chart
- Data from yfinance `funds_data.top_holdings`

### 🔔 Alerts
- Full alert log: movements, rating changes, 52W highs/lows, earnings proximity, digests
- Filter by alert type

### 📅 Weekly Report
- **🤖 AI Weekly Brief**: 120–150 word plain-English summary generated by Claude (Anthropic API) every Saturday, covering the week's earnings calls, macro events, sentiment, and top analyst upside opportunities
- **Sentiment banner**: Fear & Greed score, VIX, VSTOXX with colour-coded risk level
- **Analyst Targets table**: all holdings sorted by upside %, with 52W range bar and consensus grade
- **Earnings Calls**: next week's schedule with company name, quarter, EPS estimate, revenue estimate
- **Dividend Events**: ex-dates, amounts (€/£/$), pay dates for next week
- **Ex-Dividend Calendar**: rolling 4-week forward view of all upcoming ex-dates across all holdings
- **Stock Splits**: next week
- **Macro Event Calendar**: ECB decisions + press conferences, FOMC, US CPI, US NFP, Eurozone HICP — next 4 weeks, filterable by impact/currency

### ⚙ Configure
- Add/remove stocks and ETFs via the UI
- Generate and download updated `portfolio_config.json`

---

## 📧 Email Alerts

All emails sent via SMTP — configured via GitHub Secrets.

| Alert type | Trigger |
|---|---|
| Morning Digest | Daily 08:15 CET — full portfolio snapshot + news headlines |
| Movement Alert | Stock moves ±3% from morning baseline |
| Rating Change | New broker upgrade/downgrade detected today (US stocks) |
| 52W High/Low | Holding within 0.5% of 52-week high or low (once per day per ticker) |
| Earnings Alert | Holding has earnings within 2 days |
| Weekly Summary | Every Saturday ~09:30 CET — movers, calendar, AI brief |

---

## 🔐 Security

- Dashboard protected by client-side password (stored in `sessionStorage`)
- All credentials and API keys stored as GitHub Secrets — never in config files
- `portfolio_config.json` contains no secrets

---

## 💹 Portfolio Holdings

### Stocks (34 active)

| Ticker | Name | Exchange |
|---|---|---|
| MSFT | Microsoft | NASDAQ |
| GOOG | Alphabet (Google) | NASDAQ |
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
| BTC-USD | Bitcoin | — |

> BTC-USD, GC=F (Gold), SI=F (Silver) are tracked for price only — no fundamentals or ratings.

### ETFs (5)

| Ticker | Name | Exchange |
|---|---|---|
| SPYY.DE | SPDR MSCI ACWI UCITS ETF | XETRA |
| EUNK.DE | iShares Core MSCI Europe UCITS ETF | XETRA |
| QDVE.DE | iShares S&P 500 IT Sector UCITS ETF | XETRA |
| IS3N.DE | iShares Core MSCI EM IMI UCITS ETF | XETRA |
| SEMI.AS | iShares MSCI Global Semiconductors UCITS ETF | Euronext Amsterdam |

---

## 🛠 Tech Stack

| Component | Technology |
|---|---|
| Data — prices, fundamentals, news | yfinance (free, no API key) |
| Data — macro event dates | FRED API (free key, optional) |
| AI weekly brief | Anthropic Claude API (claude-sonnet) |
| Email | SMTP (Gmail or any provider) |
| Hosting | GitHub Pages (free) |
| Automation | GitHub Actions (free tier) |
| Language | Python 3.11 + vanilla HTML/JS/CSS |
| Dependencies | `yfinance`, `requests`, `lxml`, `mstarpy`, `anthropic` |

---

## ⚙ GitHub Secrets Required

| Secret | Used by | Description |
|---|---|---|
| `EMAIL_FROM` | All workflows | SMTP sender address |
| `EMAIL_PASSWORD` | All workflows | SMTP password or app password |
| `EMAIL_TO` | All workflows | Recipient email address |
| `ANTHROPIC_API_KEY` | Saturday summary | Claude API key for AI weekly brief |
| `FRED_API_KEY` | Fundamentals | FRED key for CPI/NFP/HICP dates (optional — free at fred.stlouisfed.org) |

---

## 📅 Summer / Winter Time

Austria switches to CEST (UTC+2) in late March and back to CET (UTC+1) in late October. All workflow cron schedules are in UTC — when CEST is active, subtract 2 hours from the UTC time to get local time (instead of 1 hour in CET).

The cron times are currently set for **CET (UTC+1) — winter schedule**. Update each workflow's cron line by -1 hour for summer (CEST).
