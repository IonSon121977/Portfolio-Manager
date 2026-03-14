#!/usr/bin/env python3
"""
market_sentiment.py - Fetch market sentiment indicators.
Calculates a composite sentiment score (0-100) from:
  - VSTOXX  (European fear gauge)
  - VIX     (US fear gauge)
  - EUR/USD (risk appetite)
  - Euro Stoxx 50 vs 50-day MA (EU momentum)
  - DAX vs 50-day MA (German/EU momentum)
Saves to docs/data/market_sentiment.json
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from shared import save_json, DATA_DIR, log

import yfinance as yf

SENTIMENT_F = DATA_DIR / "market_sentiment.json"


def fetch_indicator(ticker: str, label: str) -> dict:
    """Fetch price + 50-day MA for a ticker."""
    try:
        t     = yf.Ticker(ticker)
        fi    = t.fast_info
        price = float(fi.last_price or fi.previous_close or 0)
        prev  = float(fi.previous_close or fi.last_price or 0)
        chg   = round(((price - prev) / prev * 100) if prev else 0, 2)

        # 50-day MA from history
        ma50 = None
        try:
            hist = t.history(period="3mo", interval="1d")
            if not hist.empty and len(hist) >= 10:
                ma50 = round(float(hist["Close"].tail(50).mean()), 4)
        except Exception:
            pass

        log.info("  " + label + " (" + ticker + "): " + str(round(price, 2)) +
                 ("  MA50=" + str(ma50) if ma50 else ""))
        return {
            "ticker":  ticker,
            "label":   label,
            "price":   round(price, 4),
            "prev":    round(prev,  4),
            "chg_pct": chg,
            "ma50":    ma50,
            "above_ma50": (price > ma50) if ma50 else None,
        }
    except Exception as e:
        log.warning("  " + label + " failed: " + str(e))
        return {"ticker": ticker, "label": label, "error": str(e)}


def calc_composite_score(indicators: dict) -> dict:
    """
    Calculate composite sentiment score 0-100.
    50 = neutral, >60 = bullish, >75 = greedy, <40 = fearful, <25 = extreme fear.

    Weights:
      VSTOXX  25%  — low volatility = bullish
      VIX     20%  — low volatility = bullish
      EURUSD  15%  — rising EUR = risk-on = bullish
      Stoxx50 25%  — above MA50 = bullish
      DAX     15%  — above MA50 = bullish
    """
    score = 50.0
    components = {}

    # ── VSTOXX (25%) — fear gauge, lower = more bullish ──────────────────
    vstoxx = indicators.get("vstoxx", {})
    vstoxx_price = vstoxx.get("price")
    if vstoxx_price and "error" not in vstoxx:
        # Historical range roughly 10-90, normal ~18-22
        # Below 15 = extreme greed, above 35 = extreme fear
        if vstoxx_price < 12:
            v_score = 90
        elif vstoxx_price < 15:
            v_score = 75
        elif vstoxx_price < 20:
            v_score = 60
        elif vstoxx_price < 25:
            v_score = 50
        elif vstoxx_price < 30:
            v_score = 35
        elif vstoxx_price < 40:
            v_score = 20
        else:
            v_score = 10
        contribution = (v_score - 50) * 0.25
        score += contribution
        components["vstoxx"] = {
            "value": vstoxx_price,
            "score": v_score,
            "contribution": round(contribution, 1),
            "interpretation": (
                "Extreme greed" if vstoxx_price < 12 else
                "Greed"         if vstoxx_price < 15 else
                "Calm"          if vstoxx_price < 20 else
                "Neutral"       if vstoxx_price < 25 else
                "Fear"          if vstoxx_price < 30 else
                "High fear"     if vstoxx_price < 40 else
                "Extreme fear"
            )
        }

    # ── VIX (20%) ─────────────────────────────────────────────────────────
    vix = indicators.get("vix", {})
    vix_price = vix.get("price")
    if vix_price and "error" not in vix:
        if vix_price < 12:
            v_score = 90
        elif vix_price < 15:
            v_score = 75
        elif vix_price < 20:
            v_score = 60
        elif vix_price < 25:
            v_score = 50
        elif vix_price < 30:
            v_score = 35
        elif vix_price < 40:
            v_score = 20
        else:
            v_score = 10
        contribution = (v_score - 50) * 0.20
        score += contribution
        components["vix"] = {
            "value": vix_price,
            "score": v_score,
            "contribution": round(contribution, 1),
            "interpretation": (
                "Extreme greed" if vix_price < 12 else
                "Greed"         if vix_price < 15 else
                "Calm"          if vix_price < 20 else
                "Neutral"       if vix_price < 25 else
                "Fear"          if vix_price < 30 else
                "High fear"     if vix_price < 40 else
                "Extreme fear"
            )
        }

    # ── EUR/USD (15%) — rising EUR = risk-on ─────────────────────────────
    eurusd = indicators.get("eurusd", {})
    eurusd_chg = eurusd.get("chg_pct")
    if eurusd_chg is not None and "error" not in eurusd:
        if eurusd_chg > 1.0:
            e_score = 80
        elif eurusd_chg > 0.3:
            e_score = 65
        elif eurusd_chg > -0.3:
            e_score = 50
        elif eurusd_chg > -1.0:
            e_score = 35
        else:
            e_score = 20
        contribution = (e_score - 50) * 0.15
        score += contribution
        components["eurusd"] = {
            "value": eurusd.get("price"),
            "chg_pct": eurusd_chg,
            "score": e_score,
            "contribution": round(contribution, 1),
            "interpretation": (
                "Risk-on"     if eurusd_chg > 0.3  else
                "Neutral"     if eurusd_chg > -0.3 else
                "Risk-off"
            )
        }

    # ── Euro Stoxx 50 vs MA50 (25%) ────────────────────────────────────────
    stoxx = indicators.get("stoxx50", {})
    stoxx_above = stoxx.get("above_ma50")
    if stoxx_above is not None and "error" not in stoxx:
        pct_from_ma = None
        if stoxx.get("ma50") and stoxx.get("price"):
            pct_from_ma = (stoxx["price"] - stoxx["ma50"]) / stoxx["ma50"] * 100

        if pct_from_ma is not None:
            if pct_from_ma > 5:
                s_score = 80
            elif pct_from_ma > 2:
                s_score = 65
            elif pct_from_ma > 0:
                s_score = 55
            elif pct_from_ma > -2:
                s_score = 45
            elif pct_from_ma > -5:
                s_score = 35
            else:
                s_score = 20
        else:
            s_score = 55 if stoxx_above else 45

        contribution = (s_score - 50) * 0.25
        score += contribution
        components["stoxx50"] = {
            "value": stoxx.get("price"),
            "ma50": stoxx.get("ma50"),
            "pct_from_ma": round(pct_from_ma, 2) if pct_from_ma else None,
            "above_ma50": stoxx_above,
            "score": s_score,
            "contribution": round(contribution, 1),
            "interpretation": (
                "Strong uptrend" if (pct_from_ma or 0) > 5  else
                "Uptrend"        if (pct_from_ma or 0) > 0  else
                "Downtrend"      if (pct_from_ma or 0) > -5 else
                "Strong downtrend"
            )
        }

    # ── DAX vs MA50 (15%) ─────────────────────────────────────────────────
    dax = indicators.get("dax", {})
    dax_above = dax.get("above_ma50")
    if dax_above is not None and "error" not in dax:
        pct_from_ma = None
        if dax.get("ma50") and dax.get("price"):
            pct_from_ma = (dax["price"] - dax["ma50"]) / dax["ma50"] * 100

        if pct_from_ma is not None:
            if pct_from_ma > 5:
                d_score = 80
            elif pct_from_ma > 2:
                d_score = 65
            elif pct_from_ma > 0:
                d_score = 55
            elif pct_from_ma > -2:
                d_score = 45
            elif pct_from_ma > -5:
                d_score = 35
            else:
                d_score = 20
        else:
            d_score = 55 if dax_above else 45

        contribution = (d_score - 50) * 0.15
        score += contribution
        components["dax"] = {
            "value": dax.get("price"),
            "ma50": dax.get("ma50"),
            "pct_from_ma": round(pct_from_ma, 2) if pct_from_ma else None,
            "above_ma50": dax_above,
            "score": d_score,
            "contribution": round(contribution, 1),
            "interpretation": (
                "Strong uptrend" if (pct_from_ma or 0) > 5  else
                "Uptrend"        if (pct_from_ma or 0) > 0  else
                "Downtrend"      if (pct_from_ma or 0) > -5 else
                "Strong downtrend"
            )
        }

    final_score = max(0, min(100, round(score)))

    if final_score >= 75:
        label = "Extreme Greed"
        color = "#52d68a"
    elif final_score >= 60:
        label = "Greed"
        color = "#a8d68a"
    elif final_score >= 45:
        label = "Neutral"
        color = "#f6ad55"
    elif final_score >= 30:
        label = "Fear"
        color = "#f56565"
    else:
        label = "Extreme Fear"
        color = "#c0392b"

    return {
        "score":       final_score,
        "label":       label,
        "color":       color,
        "components":  components,
    }


def main():
    log.info("=== Market Sentiment ===")

    indicators = {}

    log.info("Fetching VSTOXX (European fear gauge)...")
    indicators["vstoxx"] = fetch_indicator("^V2TX",     "VSTOXX")

    log.info("Fetching VIX (US fear gauge)...")
    indicators["vix"]    = fetch_indicator("^VIX",      "VIX")

    log.info("Fetching EUR/USD...")
    indicators["eurusd"] = fetch_indicator("EURUSD=X",  "EUR/USD")

    log.info("Fetching Euro Stoxx 50...")
    indicators["stoxx50"]= fetch_indicator("^STOXX50E", "Euro Stoxx 50")

    log.info("Fetching DAX...")
    indicators["dax"]    = fetch_indicator("^GDAXI",    "DAX")

    sentiment = calc_composite_score(indicators)

    log.info("Composite score: " + str(sentiment["score"]) +
             " — " + sentiment["label"])

    output = {
        "composite":  sentiment,
        "indicators": indicators,
        "updated":    datetime.utcnow().isoformat(),
    }

    save_json(SENTIMENT_F, output)
    log.info("Saved -> " + str(SENTIMENT_F))
    log.info("=== Done ===")


if __name__ == "__main__":
    main()
