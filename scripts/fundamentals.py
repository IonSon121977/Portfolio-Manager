#!/usr/bin/env python3
"""
fundamentals.py - Fetch fundamental financial data for all holdings.
Runs every 2 hours during market hours via GitHub Actions.
Saves to docs/data/fundamentals.json for use by the Vercel webapp.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from shared import (
    load_config, save_json, load_json,
    DATA_DIR, log
)

import yfinance as yf

FUNDAMENTALS_F = DATA_DIR / "fundamentals.json"


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

    # Skip commodities and crypto — no fundamentals available
    SKIP = {"BTC-USD", "GC=F", "SI=F", "ETH-USD"}
    if ticker in SKIP or "=" in ticker or ticker.endswith("-USD"):
        out["skip"] = True
        return out

    try:
        t    = yf.Ticker(ticker)
        fi   = t.fast_info

        # Price data
        price = float(fi.last_price or fi.previous_close or 0)
        prev  = float(fi.previous_close or fi.last_price or 0)
        currency = str(fi.currency or "USD").upper()
        if currency == "GBP" and price > 500:
            currency = "GBX"

        out["price_native"] = round(price, 4)
        out["prev_close"]   = round(prev, 4)
        out["currency"]     = currency
        out["change_pct"]   = round(((price - prev) / prev * 100) if prev else 0, 2)

        # FX to EUR
        from shared import to_eur
        price_eur = to_eur(price, currency)
        out["price_eur"]   = round(price_eur, 2)
        out["value_eur"]   = round(price_eur * shares, 2)

        try:
            info = t.info
            out["name"]           = info.get("shortName") or info.get("longName") or name

            # Basic ratios
            out["pe_ratio"]       = info.get("trailingPE") or info.get("forwardPE")
            out["pb_ratio"]       = info.get("priceToBook")
            out["ps_ratio"]       = info.get("priceToSalesTrailing12Months")
            out["beta"]           = info.get("beta")
            out["market_cap"]     = info.get("marketCap")
            out["eps_ttm"]        = info.get("trailingEps")

            # Dividend
            out["dividend_yield"] = info.get("dividendYield")

            # Profitability
            out["roe"]            = info.get("returnOnEquity")
            out["roa"]            = info.get("returnOnAssets")
            out["profit_margin"]  = info.get("profitMargins")

            # Financial health
            out["debt_to_equity"] = info.get("debtToEquity")
            out["current_ratio"]  = info.get("currentRatio")

            # Growth
            out["revenue_growth"] = info.get("revenueGrowth")
            out["earnings_growth"]= info.get("earningsGrowth")

            # 52-week
            out["52w_high"]       = info.get("fiftyTwoWeekHigh")
            out["52w_low"]        = info.get("fiftyTwoWeekLow")

            # Analyst
            out["sector"]         = info.get("sector", "")
            out["country"]        = info.get("country", "")

            rec_key = info.get("recommendationKey", "")
            if rec_key:
                rec_map = {
                    "strong_buy": "buy", "buy": "buy",
                    "hold": "hold", "underperform": "sell",
                    "sell": "sell", "strong_sell": "sell"
                }
                out["recommendation"] = rec_map.get(rec_key.lower(), "hold")

            out["analyst_total"]       = info.get("numberOfAnalystOpinions", 0) or 0
            out["analyst_target_mean"] = info.get("targetMeanPrice")
            out["analyst_target_high"] = info.get("targetHighPrice")
            out["analyst_target_low"]  = info.get("targetLowPrice")

            log.info("  " + ticker + " OK — P/E=" + str(out.get("pe_ratio", "--")) +
                     " ROE=" + str(out.get("roe", "--")) +
                     " margin=" + str(out.get("profit_margin", "--")))

        except Exception as e:
            log.warning("  " + ticker + " info failed: " + str(e))

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
        log.info("  " + ticker)
        data = fetch_fundamentals(h)
        results.append(data)
        if "error" not in data and not data.get("skip"):
            total_eur += data.get("value_eur", 0)

    output = {
        "holdings":  results,
        "total_eur": round(total_eur, 2),
        "updated":   datetime.utcnow().isoformat(),
        "count":     len(results),
    }

    save_json(FUNDAMENTALS_F, output)
    log.info("Saved " + str(len(results)) + " holdings to " + str(FUNDAMENTALS_F))
    log.info("Total portfolio EUR: " + "{:,.2f}".format(total_eur))
    log.info("=== Done ===")


if __name__ == "__main__":
    main()
