# 📊 Portfolio Intelligence Monitor

A fully automated personal portfolio monitoring system running on GitHub Actions with zero monthly cost. Tracks stocks and ETFs across all major European and US exchanges, sends email alerts, and provides a live dashboard.

**Dashboard:** https://ionson121977.github.io/Portfolio-Manager/

---

## 🏗 Architecture

```
GitHub Actions (5 workflows)
    ↓ fetch data via yfinance
    ↓ commit JSON to docs/data/
GitHub Pages (static dashboard)
    ↓ serves docs/index.html + docs/data/*.json
Browser (password protected)
    ↓ renders dashboard from JSON files
```

**No server. No database. No paid APIs. 100% free.**

---

## ⚡ Workflows

| Workflow | Schedule (CET) | What it does |
|---|---|---|
| **Price Digest** | 08:15 Mon–Fri | Morning digest email, saves snapshot, morning prices baseline |
| **Movement & Intelligence** | 08:45, 11:00, 13:00, 15:45, 17:00 Mon–Fri | Price movement alerts (±3%), analyst rating change alerts |
| **Intelligence Check** | 08:30, 10:30, 12:30, 14:30, 16:30 Mon–Fri | Broker ratings, Morningstar data, new rating emails |
| **Fundamentals Update** | Every 2h 08:00–18:00 Mon–Fri | Fundamentals, insider transactions, earnings surprise, sentiment |
| **Saturday Summary** | 10:00 Saturday | Weekly summary email, portfolio change, top movers, next week calendar |
| **Deploy Pages** | On push to docs/ | Publishes updated dashboard to GitHub Pages |

---

## 📁 Repository Structure

```
.github/workflows/          # 6 GitHub Actions workflow files
scripts/
  shared.py                 # Shared utilities, yfinance data fetching, email
  price_digest.py           # Morning digest + movement alerts + 52W alerts
  intelligence.py           # Broker ratings checker
  market_sentiment.py       # Composite sentiment score (VSTOXX, VIX, EUR/USD, DAX, Stoxx50)
  fundamentals.py           # Fundamentals + insider transactions + earnings history
  saturday_summary.py       # Weekly summary + next week calendar
docs/
  index.html                # Single-page dashboard (password protected)
  data/
    snapshot.json           # Latest portfolio prices and values
    intelligence.json       # Ratings and analyst data
    fundamentals.json       # Fundamental metrics per holding
    market_sentiment.json   # Composite sentiment score + 5 indicators
    weekly_report.json      # Saturday weekly report data
    alerts.json             # Alert log (last 500)
    week_open.json          # Monday open prices for weekly change calc
    52w_alerted_today.json  # 52W alert deduplication (resets daily)
portfolio_config.json       # Holdings configuration (tickers, shares, ISINs)
```

---

## 📈 Dashboard Tabs

### 🏠 Dashboard
- Total portfolio value in EUR
- Stocks and ETFs table with live prices, day change, value, analyst recommendation
- Last updated timestamp

### 📊 Stock Scores
- Investment score (0–100) for each holding calculated from P/E, P/B, ROE, margins, growth, beta, 52W performance
- Sortable, filterable, paginated table
- Click any row for full score breakdown
- Export to CSV, JSON, XML, HTML, PDF

### 🌍 Market Intelligence
- **Composite Sentiment Score** (0–100) from 5 indicators: VSTOXX, VIX, EUR/USD, Euro Stoxx 50 vs MA50, DAX vs MA50
- Analyst price targets with upside % from current price
- Short interest per holding
- Earnings surprise history (last 4 quarters — beat/miss)
- Insider transactions (last 10 per holding)
- Revenue vs Net Income trend (last 4 quarters)

### 🧠 Intelligence
- Recent analyst rating changes (today)
- News by holding

### 🗂 ETF Holdings
- Top 15 holdings per ETF

### 🔔 Alerts
- Full alert log — movements, ratings, 52W highs/lows, earnings, digests

### 📅 Weekly Report
- Week-over-week portfolio change
- Top movers of the week
- Rating changes this week
- Next week: earnings calls, dividend ex-dates, stock splits

### ⚙ Configure
- Add/remove stocks and ETFs
- Generate `portfolio_config.json` for committing to repo

---

## 📧 Email Alerts

All emails sent via **AgentMail** (SMTP) — configured via GitHub Secrets.

| Alert type | Trigger |
|---|---|
| Morning Digest | Daily 08:15 CET with full portfolio + news |
| Movement Alert | Stock moves ±3% from morning price |
| Rating Change | New analyst upgrade/downgrade today |
| 52W High/Low | Stock within 0.5% of 52-week high or low (once per day per ticker) |
| Earnings Alert | Holding has earnings within 2 days |
| Weekly Summary | Every Saturday 10:00 CET |

---

## 🔐 Security

- Dashboard protected by password (client-side, stored in sessionStorage)
- Email credentials stored as GitHub Secrets — never in config files
- `portfolio_config.json` strips passwords before committing

---

## 💹 Portfolio Holdings

### Stocks


### ETFs


---

## 🛠 Tech Stack

| Component | Technology |
|---|---|
| Data source | yfinance (free, no API key) |
| Email | AgentMail SMTP |
| Hosting | GitHub Pages (free) |
| Automation | GitHub Actions (free tier) |
| Language | Python 3.11 + vanilla HTML/JS |
| Dependencies | `yfinance`, `requests` |

---

## ⚙ GitHub Secrets Required

| Secret | Description |
|---|---|
| `EMAIL_FROM` | AgentMail sender address |
| `EMAIL_PASSWORD` | AgentMail API key |
| `EMAIL_TO` | Your email address for alerts |

---

## 📅 Summer Time Note

Austria switches to CEST (UTC+2) at end of March and back to CET (UTC+1) at end of October.
All workflow cron times are in UTC — adjust by -1 hour during CEST period (end of March to end of October).

Current cron times are set for **CET (UTC+1)** — winter schedule.
