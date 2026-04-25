#!/usr/bin/env python3
"""
macro_calendar.py — Fetch upcoming macro events relevant to a European investor.

Sources (all free, no API key required):
  1. ForexFactory public JSON calendar  — structured events with impact/currency
  2. Hardcoded ECB + Fed schedule       — meeting dates published annually

Saves docs/data/macro_calendar.json
Runs as part of the fundamentals workflow (every 2h on weekdays).
"""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, date, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from shared import save_json, DATA_DIR, log

MACRO_F = DATA_DIR / "macro_calendar.json"

# ── IMPACT / CATEGORY HELPERS ────────────────────────────────────────────────

WATCHED_CURRENCIES = {"EUR", "USD", "GBP"}

# Events we always keep regardless of ForexFactory impact rating
ALWAYS_KEEP = {
    "cpi", "ppi", "gdp", "nfp", "non-farm", "payroll", "fomc", "ecb",
    "fed rate", "interest rate", "pmi", "inflation", "unemployment",
    "retail sales", "industrial production", "trade balance",
    "consumer confidence", "ism", "jolts", "durable goods",
    "flash pmi", "composite pmi", "services pmi", "manufacturing pmi",
    "core cpi", "core pce", "pce", "zew", "ifo",
}

def _is_relevant(event: dict) -> bool:
    """Keep high-impact EUR/USD/GBP events and always-watch event types."""
    currency = (event.get("currency") or "").upper()
    title    = (event.get("title")    or "").lower()
    impact   = (event.get("impact")   or "").lower()

    if currency not in WATCHED_CURRENCIES:
        return False
    if impact in ("high", "medium"):
        return True
    # keep named key events even if ForexFactory marks them low
    return any(kw in title for kw in ALWAYS_KEEP)


def _fmt_impact(impact: str) -> str:
    return {"high": "🔴 High", "medium": "🟡 Medium", "low": "🟢 Low"}.get(
        (impact or "").lower(), impact or "—"
    )


# ── FOREXFACTORY FETCH ───────────────────────────────────────────────────────

FF_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]

def _fetch_ff(url: str) -> list:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; portfolio-bot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        events = []
        for e in raw:
            if not _is_relevant(e):
                continue
            # ForexFactory date field: "01-27-2026" or ISO
            raw_date = e.get("date") or ""
            try:
                if "-" in raw_date and len(raw_date) == 10:
                    # try MM-DD-YYYY first, then YYYY-MM-DD
                    parts = raw_date.split("-")
                    if len(parts[0]) == 4:
                        d = raw_date          # already YYYY-MM-DD
                    else:
                        d = f"{parts[2]}-{parts[0]}-{parts[1]}"
                else:
                    d = raw_date[:10]
            except Exception:
                d = raw_date[:10]

            events.append({
                "date":     d,
                "time":     (e.get("time") or "").strip() or "All day",
                "currency": (e.get("currency") or "").upper(),
                "impact":   _fmt_impact(e.get("impact")),
                "impact_raw": (e.get("impact") or "").lower(),
                "title":    (e.get("title") or "").strip(),
                "forecast": str(e.get("forecast") or ""),
                "previous": str(e.get("previous") or ""),
                "source":   "ForexFactory",
            })
        log.info(f"  ForexFactory {url.split('/')[-1]}: {len(events)} relevant events")
        return events
    except Exception as exc:
        log.warning(f"  ForexFactory fetch failed ({url}): {exc}")
        return []


# ── ECB HARDCODED SCHEDULE ───────────────────────────────────────────────────
# Source: https://www.ecb.europa.eu/press/govcdec/mopo/2025/html/index.en.html
# Updated for 2025-2026. Re-check annually.

ECB_DATES_2025 = [
    "2025-01-30", "2025-03-06", "2025-04-17", "2025-06-05",
    "2025-07-24", "2025-09-11", "2025-10-30", "2025-12-18",
]
ECB_DATES_2026 = [
    "2026-01-29", "2026-03-05", "2026-04-16", "2026-06-04",
    "2026-07-23", "2026-09-10", "2026-10-22", "2026-12-17",
]

# ── FED FOMC HARDCODED SCHEDULE ──────────────────────────────────────────────
# Source: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
# Decision day (second day of two-day meeting).

FOMC_DATES_2025 = [
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
]
FOMC_DATES_2026 = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]


def _hardcoded_events(from_date: date, to_date: date) -> list:
    events = []
    all_ecb  = ECB_DATES_2025 + ECB_DATES_2026
    all_fomc = FOMC_DATES_2025 + FOMC_DATES_2026

    for d_str in all_ecb:
        d = date.fromisoformat(d_str)
        if from_date <= d <= to_date:
            events.append({
                "date":       d_str,
                "time":       "13:45 CET",
                "currency":   "EUR",
                "impact":     "🔴 High",
                "impact_raw": "high",
                "title":      "ECB Interest Rate Decision",
                "forecast":   "",
                "previous":   "",
                "source":     "ECB Schedule",
            })

    for d_str in all_fomc:
        d = date.fromisoformat(d_str)
        if from_date <= d <= to_date:
            events.append({
                "date":       d_str,
                "time":       "19:00 CET",
                "currency":   "USD",
                "impact":     "🔴 High",
                "impact_raw": "high",
                "title":      "Fed Interest Rate Decision (FOMC)",
                "forecast":   "",
                "previous":   "",
                "source":     "Fed Schedule",
            })

    return events


# ── DEDUPLICATE ──────────────────────────────────────────────────────────────

def _dedup(events: list) -> list:
    seen = set()
    out  = []
    for e in events:
        key = (e["date"], e["currency"], e["title"][:30].lower())
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=== Macro Calendar ===")

    today    = date.today()
    # Fetch events for next 4 weeks (covers this week + 3 more)
    to_date  = today + timedelta(weeks=4)

    # 1. ForexFactory — this week and next week
    ff_events: list = []
    for url in FF_URLS:
        ff_events.extend(_fetch_ff(url))

    # 2. Hardcoded ECB / FOMC — 4-week window
    hc_events = _hardcoded_events(today, to_date)
    log.info(f"  Hardcoded ECB/FOMC events in window: {len(hc_events)}")

    # 3. Merge: hardcoded first (authoritative for ECB/FOMC), then FF fills the rest
    all_events = _dedup(hc_events + ff_events)

    # 4. Filter to window & sort
    in_window = [
        e for e in all_events
        if today.isoformat() <= e["date"] <= to_date.isoformat()
    ]
    in_window.sort(key=lambda e: (e["date"], e["time"]))

    log.info(f"  Total events in 4-week window: {len(in_window)}")

    # 5. Group by date for easy dashboard rendering
    by_date: dict = {}
    for e in in_window:
        by_date.setdefault(e["date"], []).append(e)

    output = {
        "events":    in_window,
        "by_date":   by_date,
        "from_date": today.isoformat(),
        "to_date":   to_date.isoformat(),
        "updated":   datetime.utcnow().isoformat(),
        "count":     len(in_window),
    }

    save_json(MACRO_F, output)
    log.info(f"  Saved {len(in_window)} events -> {MACRO_F}")
    log.info("=== Done ===")


if __name__ == "__main__":
    main()
