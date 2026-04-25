#!/usr/bin/env python3
"""
intelligence.py - Triggered multiple times daily by GitHub Actions

For every holding in the portfolio (stocks + ETFs):
  1. Analyst rating changes (last 7 days) — broker-by-broker upgrades/downgrades
     Works for US tickers and major European names via Yahoo Finance.
     Falls back to synthesised entries from monthly consensus for EU mid-caps.
  2. Analyst consensus — monthly buy/hold/sell counts (works for all exchanges)
  3. Sends immediate email on new rating changes today
"""

import sys
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent))
from shared import (
    load_config, save_json, load_json,
    INTEL_F,
    get_analyst_upgrades,
    get_analyst_consensus,
    get_company_news,
    append_alert, send_email,
    rating_change_html, log
)


def main():
    log.info("=== Intelligence run ===")
    cfg        = load_config()
    intel_data = load_json(INTEL_F, {"holdings": []})
    existing   = {h["ticker"]: h for h in intel_data.get("holdings", [])}
    today      = datetime.utcnow().strftime("%Y-%m-%d")
    ratings_days_back = 7

    all_holdings = cfg["portfolio"]["stocks"] + cfg["portfolio"]["etfs"]
    updated = []

    for h in all_holdings:
        ticker = (h.get("ticker") or "").strip()
        name   = h.get("name", ticker)
        if not ticker:
            continue

        entry = existing.get(ticker, {
            "ticker":  ticker,
            "name":    name,
            "ratings": [],
        })
        entry["name"] = name

        # ── Broker upgrades/downgrades (+ consensus fallback for EU) ──────────
        log.info("  Broker ratings: " + ticker)
        new_ratings = get_analyst_upgrades(ticker, days_back=ratings_days_back)

        if new_ratings:
            seen_keys = {
                (r["date"], r["firm"], r["to_grade"])
                for r in entry.get("ratings", [])
            }
            truly_new = [
                r for r in new_ratings
                if (r["date"], r["firm"], r["to_grade"]) not in seen_keys
            ]
            entry["ratings"]     = (new_ratings + entry.get("ratings", []))[:50]
            entry["new_ratings"] = [
                r for r in truly_new
                if r["date"] == today
                and (r.get("from_grade") or "").strip().lower() != (r.get("to_grade") or "").strip().lower()
                and r.get("to_grade")
                and r.get("action", "").lower() != "reit"
                and r.get("source", "broker") == "broker"   # only alert on real broker changes
            ]

            for r in entry["new_ratings"]:
                log.info(
                    "  NEW RATING: " + ticker + " " +
                    r.get("firm", "") + " -> " + r.get("to_grade", "")
                )
                append_alert(
                    "rating_change", ticker,
                    r.get("firm", "") + ": " +
                    (r.get("from_grade") or "--") + " -> " + r.get("to_grade", "")
                )
                send_email(
                    "[RATING] " + ticker + " " +
                    r.get("action", "").upper() + " -> " + r.get("to_grade", ""),
                    rating_change_html(ticker, name, [r]),
                    cfg
                )
        else:
            entry["new_ratings"] = []

        # ── Monthly consensus (buy/hold/sell counts) — all exchanges ──────────
        log.info("  Analyst consensus: " + ticker)
        consensus = get_analyst_consensus(ticker)
        if consensus:
            entry["consensus"] = consensus
            log.info(
                "    " + ticker + " consensus: " +
                str(consensus.get("latest", {}).get("grade", "?")) +
                " trend=" + str(consensus.get("trend", "?"))
            )
        else:
            # keep previous consensus if fresh fetch returned nothing
            if "consensus" not in entry:
                entry["consensus"] = {}

        # ── News (multi-source: yfinance, Google, Bing, Seeking Alpha) ──────────
        log.info("  News: " + ticker)
        news = get_company_news(
            ticker,
            days_back=3,          # last 3 days — more than digest's 1 day
            max_articles=6,
            holding_name=name,
        )
        entry["news"] = news
        log.info("    " + ticker + ": " + str(len(news)) + " article(s)")

        updated.append(entry)

    save_json(INTEL_F, {"holdings": updated, "updated": today})
    log.info("Intelligence saved -> " + str(INTEL_F))
    log.info("=== Done ===")


if __name__ == "__main__":
    main()
