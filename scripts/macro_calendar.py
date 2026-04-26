#!/usr/bin/env python3
"""
macro_calendar.py — Upcoming macro events relevant to a European equity investor.

Two sources:
  1. HARDCODED — ECB rate decisions + press conferences, FOMC decisions.
     Published annually, never change mid-year. Always present regardless
     of whether a FRED key is available.

  2. FRED API (requires FRED_API_KEY env var, free key at fred.stlouisfed.org)
     Fetches official future release dates for:
       • US CPI            (release_id=10,  BLS)
       • US NFP            (release_id=50,  BLS — Employment Situation)
       • Eurozone HICP CPI (release_id=251, Eurostat via FRED)
     All three use the same FRED key and the same endpoint — no separate
     Eurostat API needed.

     If FRED_API_KEY is not set, only ECB + FOMC events are shown.

Saves docs/data/macro_calendar.json
Runs as part of the fundamentals workflow (every 2h on weekdays).
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, date, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from shared import save_json, DATA_DIR, log

MACRO_F = DATA_DIR / "macro_calendar.json"


# ── HARDCODED: ECB ────────────────────────────────────────────────────────────
# Source: https://www.ecb.europa.eu/press/govcdec/mopo/
# Decision 13:15 CET, Press Conference 13:45 CET (same day)
ECB_DATES = [
    "2025-01-30","2025-03-06","2025-04-17","2025-06-05",
    "2025-07-24","2025-09-11","2025-10-30","2025-12-18",
    "2026-01-29","2026-03-05","2026-04-16","2026-06-04",
    "2026-07-23","2026-09-10","2026-10-22","2026-12-17",
]

# ── HARDCODED: FOMC ───────────────────────────────────────────────────────────
# Source: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
# Decision ~20:00 CET, Press Conference ~20:30 CET
FOMC_DATES = [
    "2025-01-29","2025-03-19","2025-05-07","2025-06-18",
    "2025-07-30","2025-09-17","2025-10-29","2025-12-10",
    "2026-01-28","2026-03-18","2026-04-29","2026-06-17",
    "2026-07-29","2026-09-16","2026-10-28","2026-12-09",
]


# ── FRED: US CPI + NFP ────────────────────────────────────────────────────────

FRED_RELEASES = [
    {"release_id": 10,  "title": "US CPI (Consumer Price Index)",
     "currency": "USD", "time": "14:30 CET", "source": "BLS via FRED"},
    {"release_id": 50,  "title": "US Non-Farm Payrolls (NFP)",
     "currency": "USD", "time": "14:30 CET", "source": "BLS via FRED"},
    {"release_id": 251, "title": "Eurozone HICP (Flash CPI)",
     "currency": "EUR", "time": "11:00 CET", "source": "Eurostat via FRED"},
]


def _fetch_fred_dates(release_id: int, api_key: str,
                      from_date: str, to_date: str) -> list:
    """
    Fetch future release dates for a FRED release via fred/release/dates.
    include_release_dates_with_no_data=true is required to get future dates.
    """
    url = ("https://api.stlouisfed.org/fred/release/dates?"
           + urllib.parse.urlencode({
               "release_id":   release_id,
               "realtime_start": from_date,
               "realtime_end":   to_date,
               "include_release_dates_with_no_data": "true",
               "sort_order":   "asc",
               "file_type":    "json",
               "api_key":      api_key,
           }))
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "portfolio-bot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        dates = [
            item["date"]
            for item in data.get("release_dates", [])
            if from_date <= item.get("date", "") <= to_date
        ]
        log.info(f"  FRED release {release_id}: {len(dates)} dates in window")
        return dates
    except Exception as e:
        log.warning(f"  FRED release {release_id} failed: {e}")
        return []


def _fetch_fred_events(from_date: str, to_date: str) -> list:
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        log.warning("  FRED_API_KEY not set — skipping CPI/NFP dates")
        return []

    events = []
    for rel in FRED_RELEASES:
        dates = _fetch_fred_dates(rel["release_id"], api_key, from_date, to_date)
        for d in dates:
            events.append({
                "date":       d,
                "time":       rel["time"],
                "currency":   rel["currency"],
                "impact":     "🔴 High",
                "impact_raw": "high",
                "title":      rel["title"],
                "forecast":   "",
                "previous":   "",
                "source":     rel["source"],
            })
    return events


# ── BUILD FULL EVENT LIST ─────────────────────────────────────────────────────

def _build_hardcoded(from_date: str, to_date: str) -> list:
    events = []

    def _add(d, currency, title, time_cet, source):
        if from_date <= d <= to_date:
            events.append({
                "date":       d,
                "time":       time_cet,
                "currency":   currency,
                "impact":     "🔴 High",
                "impact_raw": "high",
                "title":      title,
                "forecast":   "",
                "previous":   "",
                "source":     source,
            })

    for d in ECB_DATES:
        _add(d, "EUR", "ECB Interest Rate Decision", "13:15 CET", "ECB")
        _add(d, "EUR", "ECB Press Conference",       "13:45 CET", "ECB")
    for d in FOMC_DATES:
        _add(d, "USD", "Fed Interest Rate Decision (FOMC)", "20:00 CET",
             "Federal Reserve")
    return events


def main():
    log.info("=== Macro Calendar ===")

    today   = date.today()
    to_date = today + timedelta(weeks=4)
    fd      = today.isoformat()
    td      = to_date.isoformat()

    # 1. Hardcoded ECB + FOMC — always present
    events = _build_hardcoded(fd, td)
    log.info(f"  Hardcoded events (ECB+FOMC): {len(events)}")

    # 2. FRED — US CPI + NFP + Eurozone HICP (requires FRED_API_KEY)
    fred_events = _fetch_fred_events(fd, td)
    events.extend(fred_events)

    # Deduplicate by (date, title[:30]) then sort
    seen = set()
    unique = []
    for e in events:
        key = (e["date"], e["title"][:30])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    unique.sort(key=lambda e: (e["date"], e["time"]))

    by_date = {}
    for e in unique:
        by_date.setdefault(e["date"], []).append(e)

    save_json(MACRO_F, {
        "events":    unique,
        "by_date":   by_date,
        "from_date": fd,
        "to_date":   td,
        "updated":   datetime.utcnow().isoformat(),
        "count":     len(unique),
    })
    log.info(f"  Saved {len(unique)} events -> {MACRO_F}")
    log.info("=== Done ===")


if __name__ == "__main__":
    main()
