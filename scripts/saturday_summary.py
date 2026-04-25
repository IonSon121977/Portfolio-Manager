#!/usr/bin/env python3
"""
saturday_summary.py - Triggered every Saturday at 10:00 CET

Sends weekly roundup email:
  - Portfolio total + week-over-week change
  - Top movers of the week
  - Analyst rating changes from past 5 days
  - News from past 5 days
  - Next week: earnings, dividends, splits
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, date
import os
import json
import urllib.request

sys.path.insert(0, str(Path(__file__).parent))
from shared import (
    load_config, load_json, save_json, append_alert, send_email,
    SNAPSHOT_F, INTEL_F, DATA_DIR,
    get_stock_data, get_earnings_calendar, get_dividends, get_stock_splits,
    saturday_summary_html, next_week_calendar_html,
    log
)
import time

WEEK_OPEN_F = DATA_DIR / "week_open.json"


def next_weekday_range():
    today       = date.today()
    days_to_mon = (7 - today.weekday()) % 7 or 7
    next_mon    = today + timedelta(days=days_to_mon)
    next_fri    = next_mon + timedelta(days=4)
    return next_mon.isoformat(), next_fri.isoformat()


def fmt_date(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%a %d %b")
    except Exception:
        return d


def build_week_movements(snapshot: dict, week_open: dict) -> list:
    now_map = {
        s["ticker"]: s
        for s in snapshot.get("stocks", []) + snapshot.get("etfs", [])
        if "error" not in s and s.get("price_eur")
    }
    open_map = {
        s["ticker"]: s
        for s in week_open.get("stocks", []) + week_open.get("etfs", [])
        if "error" not in s and s.get("price_eur")
    }
    moves = []
    for ticker, now in now_map.items():
        opened = open_map.get(ticker)
        if not opened:
            continue
        p_now  = now["price_eur"]
        p_open = opened["price_eur"]
        if p_open == 0:
            continue
        moves.append({
            "ticker":   ticker,
            "name":     now.get("name", ticker),
            "from_eur": round(p_open, 2),
            "to_eur":   round(p_now,  2),
            "move_pct": round((p_now - p_open) / p_open * 100, 2),
        })
    return sorted(moves, key=lambda x: abs(x["move_pct"]), reverse=True)


def fetch_next_week_calendar(cfg: dict) -> dict:
    next_mon, next_fri = next_weekday_range()
    all_holdings       = cfg["portfolio"]["stocks"] + cfg["portfolio"]["etfs"]

    earnings_all  = []
    dividends_all = []
    splits_all    = []

    log.info("  Fetching calendar for next week: " + next_mon + " -> " + next_fri)

    for h in all_holdings:
        ticker = (h.get("ticker") or "").strip()
        name   = h.get("name", ticker)
        if not ticker:
            continue

        log.info("    " + ticker)

        for e in get_earnings_calendar(ticker, from_date=next_mon, to_date=next_fri):
            earnings_all.append(dict(e, ticker=ticker, name=name))

        for d in get_dividends(ticker, from_date=next_mon, to_date=next_fri):
            dividends_all.append(dict(d, ticker=ticker, name=name))

        for s in get_stock_splits(ticker, from_date=next_mon, to_date=next_fri):
            splits_all.append(dict(s, ticker=ticker, name=name))

    earnings_all.sort(key=lambda x: x.get("date", ""))
    dividends_all.sort(key=lambda x: x.get("ex_date", ""))
    splits_all.sort(key=lambda x: x.get("date", ""))

    log.info(
        "  Calendar: " + str(len(earnings_all)) + " earnings, " +
        str(len(dividends_all)) + " dividends, " +
        str(len(splits_all)) + " splits"
    )
    return {
        "earnings":  earnings_all,
        "dividends": dividends_all,
        "splits":    splits_all,
        "next_mon":  next_mon,
        "next_fri":  next_fri,
    }


def fetch_dividend_calendar_4w(cfg: dict) -> list:
    """
    Fetch upcoming ex-dividend dates for all holdings over the next 4 weeks.
    Returns a flat list sorted by ex_date, each entry includes ticker, name,
    ex_date, pay_date, amount, currency.
    """
    from_date    = date.today().isoformat()
    to_date      = (date.today() + timedelta(weeks=4)).isoformat()
    all_holdings = cfg["portfolio"]["stocks"] + cfg["portfolio"]["etfs"]
    results      = []

    log.info("  Fetching 4-week dividend calendar: " + from_date + " -> " + to_date)

    for h in all_holdings:
        ticker = (h.get("ticker") or "").strip()
        name   = h.get("name", ticker)
        if not ticker:
            continue
        for d in get_dividends(ticker, from_date=from_date, to_date=to_date):
            results.append(dict(d, ticker=ticker, name=name))

    results.sort(key=lambda x: x.get("ex_date", ""))
    log.info("  4-week dividend calendar: " + str(len(results)) + " events")
    return results

def generate_ai_brief(calendar: dict, snapshot: dict, week_movements: list,
                      sentiment: dict, fundamentals: dict) -> str:
    """
    Call the Anthropic API (via OpenRouter) to generate a 120-150 word
    plain-English weekly brief. Returns empty string on any failure.
    Requires ANTHROPIC_API_KEY or OPENROUTER_API_KEY env var.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        log.warning("  AI brief skipped: no ANTHROPIC_API_KEY or OPENROUTER_API_KEY set")
        return ""

    # Determine endpoint + model based on which key is present
    if os.environ.get("ANTHROPIC_API_KEY"):
        url     = "https://api.anthropic.com/v1/messages"
        model   = "claude-sonnet-4-20250514"
        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
        }
    else:
        url     = "https://openrouter.ai/api/v1/chat/completions"
        model   = "anthropic/claude-3-5-haiku"
        headers = {
            "Content-Type":  "application/json",
            "Authorization": "Bearer " + api_key,
        }

    next_mon  = calendar["next_mon"]
    next_fri  = calendar["next_fri"]
    earnings  = calendar["earnings"]
    dividends = calendar["dividends"]

    # Sentiment
    comp      = (sentiment or {}).get("composite", {})
    sent_score = comp.get("score")
    sent_label = comp.get("label", "")
    indicators = (sentiment or {}).get("indicators", {})
    vix_val    = (indicators.get("vix")    or {}).get("value")
    vstoxx_val = (indicators.get("vstoxx") or {}).get("value")

    # Top movers (week just ended)
    top_up   = [m for m in week_movements if m["move_pct"] > 0][:3]
    top_dn   = [m for m in week_movements if m["move_pct"] < 0][-3:]
    movers_str = ""
    if top_up:
        movers_str += "Best this week: " + ", ".join(
            f"{m['ticker']} +{m['move_pct']:.1f}%" for m in top_up)
    if top_dn:
        movers_str += " | Worst: " + ", ".join(
            f"{m['ticker']} {m['move_pct']:.1f}%" for m in top_dn)

    # Analyst upside from fundamentals
    holdings = (fundamentals or {}).get("holdings", [])
    upside_list = sorted(
        [h for h in holdings if h.get("analyst_upside") is not None and not h.get("error")],
        key=lambda h: h["analyst_upside"], reverse=True
    )
    top_upside = ", ".join(
        f"{h['ticker']} +{h['analyst_upside']:.1f}%" for h in upside_list[:3]
    ) if upside_list else "none"
    low_upside = ", ".join(
        f"{h['ticker']} {h['analyst_upside']:.1f}%" for h in upside_list[-3:]
    ) if upside_list else "none"

    earn_str = "; ".join(
        f"{e['ticker']} on {e['date']}"
        + (f" (EPS est. {e['eps_estimate']:.2f})" if e.get("eps_estimate") else "")
        for e in earnings
    ) or "None"

    div_str = "; ".join(
        f"{d['ticker']} ex-div {d['ex_date']}"
        + (f" {d['amount']:.4f} {d.get('currency','')}" if d.get("amount") else "")
        for d in dividends
    ) or "None"

    prompt = (
        "You are a concise portfolio analyst. Write a 120-150 word plain-English briefing "
        "for a private European investor reviewing their equity portfolio for the week ahead. "
        "Do NOT use bullet points or markdown. Write in flowing prose. Be specific and actionable. "
        "Reference specific tickers when relevant.\n\n"
        f"Week ahead: {fmt_date(next_mon)} to {fmt_date(next_fri)}\n"
        f"Market sentiment: {sent_score}/100 ({sent_label}) | "
        f"VIX: {vix_val:.1f if vix_val else '?'} | "
        f"VSTOXX: {vstoxx_val:.1f if vstoxx_val else '?'}\n"
        f"Week just ended — {movers_str or 'no movement data'}\n"
        f"Earnings calls next week: {earn_str}\n"
        f"Ex-dividend dates next week: {div_str}\n"
        f"Highest analyst upside: {top_upside}\n"
        f"Lowest analyst upside: {low_upside}\n\n"
        "Write the brief now. Start directly with the content, no preamble."
    )

    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            body = json.dumps({
                "model":      model,
                "max_tokens": 300,
                "messages":   [{"role": "user", "content": prompt}],
            }).encode()
        else:
            body = json.dumps({
                "model":    model,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()

        req  = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        # Anthropic format
        if "content" in data:
            text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        # OpenRouter / OpenAI format
        else:
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        text = text.strip()
        log.info(f"  AI brief generated ({len(text)} chars)")
        return text

    except Exception as e:
        log.warning("  AI brief failed: " + str(e))
        return ""


def main():
    log.info("=== Saturday Weekly Summary ===")
    cfg = load_config()
    snapshot   = load_json(SNAPSHOT_F, {"stocks": [], "etfs": [], "total_eur": 0})
    week_open  = load_json(WEEK_OPEN_F, {})
    intel_data = load_json(INTEL_F, {"holdings": []})
    sentiment  = load_json(DATA_DIR / "market_sentiment.json",  {})
    fundamentals = load_json(DATA_DIR / "fundamentals.json",    {})
    if week_open:
        snapshot["week_start_eur"] = week_open.get("total_eur")
        log.info(
            "  Week: EUR " + "{:,.2f}".format(snapshot["week_start_eur"]) +
            "  ->  EUR " + "{:,.2f}".format(snapshot["total_eur"])
        )
    else:
        log.info("  No week_open.json - week change omitted")

    week_movements = build_week_movements(snapshot, week_open) if week_open else []
    log.info(str(len(week_movements)) + " movers computed")

    log.info("--- Fetching next-week calendar ---")
    calendar = fetch_next_week_calendar(cfg)
    next_mon = calendar["next_mon"]
    next_fri = calendar["next_fri"]

    log.info("--- Fetching 4-week dividend calendar ---")
    dividend_calendar_4w = fetch_dividend_calendar_4w(cfg)



    log.info("--- Building and sending Saturday email ---")
    past_html = saturday_summary_html(snapshot, intel_data, week_movements)
    cal_html  = next_week_calendar_html(calendar, fmt_date(next_mon), fmt_date(next_fri))

    news_marker   = "<h2 style='font-size:14px;color:#f0f2f5;margin:24px 0 12px'>News This Week</h2>"
    footer_marker = "<p style='color:#4a5568;font-size:10px;margin-top:24px'>"

    if news_marker in past_html:
        combined_html = past_html.replace(news_marker, cal_html + news_marker, 1)
    else:
        combined_html = past_html.replace(footer_marker, cal_html + footer_marker, 1)

    now_label = datetime.utcnow().strftime("%d %b %Y")
    sent = send_email(
        "Weekly Summary - " + now_label,
        combined_html,
        cfg
    )
    if sent:
        append_alert(
            "weekly_summary", "",
            "Weekly summary sent - " +
            str(len(calendar["earnings"])) + " earnings, " +
            str(len(calendar["dividends"])) + " dividends, " +
            str(len(calendar["splits"])) + " splits next week"
        )

    log.info("--- Generating AI weekly brief ---")
    ai_brief = generate_ai_brief(calendar, snapshot, week_movements, sentiment, fundamentals)

   # Save weekly_report.json for the dashboard
    WEEKLY_F = DATA_DIR / "weekly_report.json"

    # Deduplicate by ticker — keep all events per ticker (bug fix: dict overwrite)
    earn_map = {}
    for e in calendar["earnings"]:
        earn_map.setdefault(e["ticker"], []).append(e)

    div_map = {}
    for d in calendar["dividends"]:
        div_map.setdefault(d["ticker"], []).append(d)

    split_map = {}
    for s in calendar["splits"]:
        split_map.setdefault(s["ticker"], []).append(s)

    save_json(WEEKLY_F, {
      "week_from":          fmt_date(next_mon),
      "week_to":            fmt_date(next_fri),
      "week_from_iso":      next_mon,
      "week_to_iso":        next_fri,
      "earnings":           earn_map,
      "dividends":          div_map,
      "splits":             split_map,
      "ipos":               [],
      "dividend_calendar":  dividend_calendar_4w,
      "ai_brief":           ai_brief,
      "generated":          datetime.utcnow().isoformat(),
    })
    log.info("Weekly report JSON saved -> " + str(WEEKLY_F))
    log.info("=== Done ===")


if __name__ == "__main__":
    main()

