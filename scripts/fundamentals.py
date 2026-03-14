#!/usr/bin/env python3
"""
fundamentals.py - Fetch fundamental + decision-support data for all holdings.
Runs every 2 hours during market hours via GitHub Actions.
Saves to docs/data/fundamentals.json
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from shared import (
    load_config, save_json,
    DATA_DIR, log
)

import yfinance as yf

FUNDAMENTALS_F = DATA_DIR / "fundamentals.json"
SKIP_TICKERS   = {"BTC-USD", "GC=F", "SI=F", "ETH-USD"}


def safe(val, decimals=2):
    try:
        return round(float(val), decimals) if val is not None else None
    except Exception:
        return None


def fetch_earnings_surprise(t) -> list:
    """Last 4 quarters: EPS estimate vs actual — beat/miss history."""
    try:
        df = t.earnings_history
        if df is None or df.empty:
            return []
        results = []
        for _, row in df.tail(4).iterrows():
            est = row.get("epsEstimate")
            act = row.get("epsActual")
            if est is None or act is None:
                continue
            surprise_pct = ((act - est) / abs(est) * 100) if est != 0 else 0
            results.append({
                "period":       str(row.get("period", "")),
                "eps_estimate": safe(est, 3),
                "eps_actual":   safe(act, 3),
                "surprise_pct": safe(surprise_pct, 1),
                "beat":         bool(act >= est),
            })
        return results
    except Exception as e:
        log.warning("  earnings_surprise failed: " + str(e))
        return []


def fetch_revenue_earnings_trend(t) -> list:
    """Quarterly revenue and net income for last 4 quarters."""
    try:
        df = t.quarterly_financials
        if df is None or df.empty:
            return []
        results = []
        cols = list(df.columns[:4])
        for col in cols:
            rev = df.loc["Total Revenue", col] if "Total Revenue" in df.index else None
            net = df.loc["Net Income",    col] if "Net Income"    in df.index else None
            results.append({
                "period":     str(col)[:10],
                "revenue":    int(rev) if rev is not None else None,
                "net_income": int(net) if net is not None else None,
            })
        return list(reversed(results))
    except Exception as e:
        log.warning("  revenue_earnings_trend failed: " + str(e))
        return []


def fetch_insider_transactions(t) -> list:
    """Recent insider buy/sell transactions (last 10)."""
    try:
        df = t.insider_transactions
        if df is None or df.empty:
            return []
        results = []
        for _, row in df.head(10).iterrows():
            shares = row.get("Shares")
            value  = row.get("Value")
            results.append({
                "date":        str(row.get("Start Date", ""))[:10],
                "insider":     str(row.get("Insider",     ""))[:30],
                "title":       str(row.get("Position",    "") or "")[:20],
                "transaction": str(row.get("Transaction", "")),
                "shares":      int(shares) if shares is not None else None,
                "value_usd":   int(value)  if value  is not None else None,
            })
        return results
    except Exception as e:
        log.warning("  insider_transactions failed: " + str(e))
        return []


def fetch_fundamentals(holding: dict) -> dict:
    ticker = holding.get("ticker", "").strip()
    name   = holding.get("name", ticker)
    isin   = holding.get("isin", "")
    shares = holding.get("shares", 0)

    out = {
        "ticker":    ticker,
        "name":      name,
        "isin":      isin,
        "shares":    shares,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if not ticker:
        return out

    if ticker in SKIP_TICKERS or "=" in ticker or ticker.endswith("-USD"):
        out["skip"] = True
        return out

    try:
        t  = yf.Ticker(ticker)
        fi = t.fast_info

        price    = float(fi.last_price or fi.previous_close or 0)
        prev     = float(fi.previous_close or fi.last_price or 0)
        currency = str(fi.currency or "USD").upper()
        if currency == "GBP" and price > 500:
            currency = "GBX"

        out["price_native"] = safe(price, 4)
        out["prev_close"]   = safe(prev,  4)
        out["currency"]     = currency
        out["change_pct"]   = safe(((price - prev) / prev * 100) if prev else 0)

        from shared import to_eur, _get_fx_rate
        price_eur      = to_eur(price, currency)
        out["price_eur"]   = safe(price_eur)
        out["value_eur"]   = safe(price_eur * shares)

        try:
            info = t.info
            out["name"] = info.get("shortName") or info.get("longName") or name

            # Basic ratios
            out["pe_ratio"]       = safe(info.get("trailingPE") or info.get("forwardPE"))
            out["pb_ratio"]       = safe(info.get("priceToBook"))
            out["ps_ratio"]       = safe(info.get("priceToSalesTrailing12Months"))
            out["beta"]           = safe(info.get("beta"))
            out["market_cap"]     = info.get("marketCap")
            out["eps_ttm"]        = safe(info.get("trailingEps"), 3)
            out["dividend_yield"] = safe(info.get("dividendYield"), 4)

            # Profitability
            out["roe"]           = safe(info.get("returnOnEquity"),  4)
            out["roa"]           = safe(info.get("returnOnAssets"),  4)
            out["profit_margin"] = safe(info.get("profitMargins"),   4)
            out["gross_margin"]  = safe(info.get("grossMargins"),    4)
            out["ebitda_margin"] = safe(info.get("ebitdaMargins"),   4)

            # Financial health
            out["debt_to_equity"] = safe(info.get("debtToEquity"))
            out["current_ratio"]  = safe(info.get("currentRatio"))
            out["quick_ratio"]    = safe(info.get("quickRatio"))
            out["free_cashflow"]  = info.get("freeCashflow")

            # Growth
            out["revenue_growth"]  = safe(info.get("revenueGrowth"),  4)
            out["earnings_growth"] = safe(info.get("earningsGrowth"), 4)

            # Short interest
            out["short_ratio"]     = safe(info.get("shortRatio"))
            out["short_pct_float"] = safe(info.get("shortPercentOfFloat"), 4)
            out["shares_short"]    = info.get("sharesShort")

            # 52-week
            out["52w_high"] = safe(info.get("fiftyTwoWeekHigh"))
            out["52w_low"]  = safe(info.get("fiftyTwoWeekLow"))

            # Analyst
            out["sector"]  = info.get("sector", "")
            out["country"] = info.get("country", "")

            rec_key = info.get("recommendationKey", "")
            if rec_key:
                rec_map = {
                    "strong_buy": "buy", "buy": "buy",
                    "hold": "hold", "underperform": "sell",
                    "sell": "sell", "strong_sell": "sell"
                }
                out["recommendation"] = rec_map.get(rec_key.lower(), "hold")

            out["analyst_total"]       = info.get("numberOfAnalystOpinions", 0) or 0
            out["analyst_target_mean"] = safe(info.get("targetMeanPrice"))
            out["analyst_target_high"] = safe(info.get("targetHighPrice"))
            out["analyst_target_low"]  = safe(info.get("targetLowPrice"))

            # Analyst upside % — current price vs mean target in EUR
            if out["analyst_target_mean"] and price_eur and price_eur > 0:
                fx = _get_fx_rate(currency)
                target_eur = out["analyst_target_mean"] * fx
                out["analyst_upside_pct"] = safe(
                    (target_eur - price_eur) / price_eur * 100
                )
            else:
                out["analyst_upside_pct"] = None

            log.info("  " + ticker + " OK — P/E=" + str(out.get("pe_ratio", "--")) +
                     "  short=" + str(out.get("short_pct_float", "--")) +
                     "  upside=" + str(out.get("analyst_upside_pct", "--")) + "%")

        except Exception as e:
            log.warning("  " + ticker + " info failed: " + str(e))

        # Extended data
        out["earnings_surprise"]      = fetch_earnings_surprise(t)
        out["revenue_earnings_trend"] = fetch_revenue_earnings_trend(t)
        out["insider_transactions"]   = fetch_insider_transactions(t)

    except Exception as e:
        out["error"] = str(e)
        log.warning("  " + ticker + " FAIL: " + str(e))

    return out


def main():
    log.info("=== Fundamentals update ===")
    cfg          = load_config()
    all_holdings = cfg["portfolio"]["stocks"] + cfg["portfolio"]["etfs"]
    log.info("Holdings: " + str(len(all_holdings)))

    results   = []
    total_eur = 0.0

    for h in all_holdings:
        ticker = (h.get("ticker") or "").strip()
        if not ticker:
            continue
        log.info("Fetching: " + ticker)
        data = fetch_fundamentals(h)
        results.append(data)
        if "error" not in data and not data.get("skip"):
            total_eur += data.get("value_eur") or 0

    output = {
        "holdings":  results,
        "total_eur": round(total_eur, 2),
        "updated":   datetime.utcnow().isoformat(),
        "count":     len(results),
    }

    save_json(FUNDAMENTALS_F, output)
    log.info("Saved " + str(len(results)) + " holdings -> " + str(FUNDAMENTALS_F))
    log.info("Total portfolio EUR: " + "{:,.2f}".format(total_eur))
    log.info("=== Done ===")


if __name__ == "__main__":
    main()
