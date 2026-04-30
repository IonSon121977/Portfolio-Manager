"""
shared.py -- All data via yfinance (free, no API key needed)
Supports all exchanges: US, XETRA (.DE), Euronext (.PA), LSE (.L), AMS (.AS), STO (.ST)
"""

import os, json, time, smtplib, logging
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("portfolio")

# -- PATHS --------------------------------------------------------------------
ROOT       = Path(__file__).parent.parent
CONFIG_F   = ROOT / "portfolio_config.json"
DATA_DIR   = ROOT / "docs" / "data"
ALERTS_F   = DATA_DIR / "alerts.json"
SNAPSHOT_F = DATA_DIR / "snapshot.json"
INTEL_F    = DATA_DIR / "intelligence.json"
RATINGS_F  = DATA_DIR / "ratings_history.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# -- CONFIG -------------------------------------------------------------------
DEFAULT_CONFIG = {
    "portfolio": {"stocks": [], "etfs": []},
    "alerts": {
        "movement_threshold_pct": 3.0,
        "email_enabled": True,
        "email_from": "",
        "email_password": "",
        "email_to": "",
    },
    "last_prices": {}
}


def load_config() -> dict:
    if CONFIG_F.exists():
        cfg = json.loads(CONFIG_F.read_text())
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
            if isinstance(v, dict):
                for kk, vv in v.items():
                    cfg[k].setdefault(kk, vv)
        env_map = {
            "EMAIL_FROM":     ("alerts", "email_from"),
            "EMAIL_PASSWORD": ("alerts", "email_password"),
            "EMAIL_TO":       ("alerts", "email_to"),
        }
        for env_var, (section, key) in env_map.items():
            if os.environ.get(env_var):
                cfg[section][key] = os.environ[env_var]
        return cfg
    cfg = DEFAULT_CONFIG.copy()
    save_config(cfg)
    return cfg


def save_config(cfg: dict):
    safe = json.loads(json.dumps(cfg))
    if os.environ.get("GITHUB_ACTIONS"):
        safe["alerts"]["email_password"] = ""
    # preserve morning_prices and last_prices — never wipe them
    CONFIG_F.write_text(json.dumps(safe, indent=2))


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))


# -- FX to EUR ----------------------------------------------------------------
_fx_cache: dict = {}


def _get_fx_rate(currency: str) -> float:
    ccy = (currency or "USD").upper().strip()
    if ccy == "EUR":
        return 1.0
    if ccy == "GBX":
        rate = _get_fx_rate("GBP") / 100.0
        _fx_cache["GBX"] = rate
        return rate
    if ccy in _fx_cache:
        return _fx_cache[ccy]
    try:
        pair = "GBPEUR=X" if ccy == "GBP" else ccy + "EUR=X"
        t    = yf.Ticker(pair)
        fi   = t.fast_info
        rate = float(fi.last_price or fi.previous_close or 1.0)
        _fx_cache[ccy] = rate
        return rate
    except Exception:
        fallbacks = {
            "USD": 0.925, "GBP": 1.17, "CHF": 1.06, "SEK": 0.087,
            "NOK": 0.086, "DKK": 0.134, "JPY": 0.006, "CAD": 0.683,
        }
        return fallbacks.get(ccy, 1.0)


def to_eur(price, currency: str) -> float:
    if price is None:
        return 0.0
    return float(price) * _get_fx_rate(currency)


# -- STOCK DATA ---------------------------------------------------------------
def get_stock_data(holding: dict, _ignored: str = "") -> dict:
    ticker = holding["ticker"]
    log.info("  " + ticker)

    out = {
        "ticker": ticker,
        "name":   holding.get("name", ticker),
    }

    try:
        t = yf.Ticker(ticker)

        # fast_info raises 'PriceHistory has no attribute _dividends' for some
        # Euronext tickers (yfinance regression). Fall back to t.history().
        price    = 0.0
        prev     = 0.0
        currency = "EUR"
        try:
            fi       = t.fast_info
            price    = float(fi.last_price    or fi.previous_close or 0)
            prev     = float(fi.previous_close or fi.last_price    or 0)
            currency = str(fi.currency or "EUR").upper()
        except Exception as fi_err:
            log.warning("  fast_info failed for " + ticker + " (" + str(fi_err) + ") — using history()")
            try:
                hist = t.history(period="5d")
                if hist is not None and not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
                if ticker.endswith(".DE") or ticker.endswith(".PA") or \
                   ticker.endswith(".AS") or ticker.endswith(".MI") or \
                   ticker.endswith(".BR") or ticker.endswith(".MC"):
                    currency = "EUR"
                elif ticker.endswith(".L"):
                    currency = "GBP"
                elif ticker.endswith(".ST"):
                    currency = "SEK"
                else:
                    currency = "USD"
            except Exception as hist_err:
                log.warning("  history() also failed for " + ticker + ": " + str(hist_err))

        if not price and not prev:
            out["error"] = "No price data from yfinance for " + ticker
            return out

        if currency == "GBP" and price > 500:
            currency = "GBX"

        chg_pct   = ((price - prev) / prev * 100) if prev else 0.0
        price_eur = to_eur(price, currency)
        prev_eur  = to_eur(prev,  currency)

        out.update({
            "price_native": round(price, 4),
            "prev_close":   round(prev,  4),
            "currency":     currency,
            "change_pct":   round(chg_pct, 2),
            "price_eur":    round(price_eur, 2),
            "prev_eur":     round(prev_eur,  2),
        })

        try:
            info = t.info
            out["name"]           = info.get("shortName") or info.get("longName") or out["name"]
            out["sector"]         = info.get("sector", "")
            out["country"]        = info.get("country", "")
            out["pe_ratio"]       = info.get("trailingPE") or info.get("forwardPE")
            out["beta"]           = info.get("beta")
            out["eps_ttm"]        = info.get("trailingEps")
            out["dividend_yield"] = info.get("dividendYield")
            out["market_cap"]     = info.get("marketCap")
            out["pb_ratio"]        = info.get("priceToBook")
            out["ps_ratio"]        = info.get("priceToSalesTrailing12Months")
            out["roe"]             = info.get("returnOnEquity")
            out["roa"]             = info.get("returnOnAssets")
            out["debt_to_equity"]  = info.get("debtToEquity")
            out["current_ratio"]   = info.get("currentRatio")
            out["profit_margin"]   = info.get("profitMargins")
            out["revenue_growth"]  = info.get("revenueGrowth")
            out["earnings_growth"] = info.get("earningsGrowth")

            rec_key = info.get("recommendationKey", "")
            if rec_key:
                rec_map = {
                    "strong_buy": "buy", "buy": "buy",
                    "hold": "hold", "underperform": "sell",
                    "sell": "sell", "strong_sell": "sell"
                }
                out["recommendation"] = rec_map.get(rec_key.lower(), "hold")

            out["analyst_total"] = info.get("numberOfAnalystOpinions", 0) or 0

            target_mean = info.get("targetMeanPrice")
            target_high = info.get("targetHighPrice")
            target_low  = info.get("targetLowPrice")
            if target_mean:
                out["analyst_target_mean"] = round(to_eur(target_mean, currency), 2)
                out["analyst_target_high"] = round(to_eur(target_high, currency), 2) if target_high else None
                out["analyst_target_low"]  = round(to_eur(target_low,  currency), 2) if target_low  else None

            w52_high = info.get("fiftyTwoWeekHigh")
            w52_low  = info.get("fiftyTwoWeekLow")
            if w52_high:
                out["52w_high"] = round(to_eur(w52_high, currency), 2)
                out["52w_low"]  = round(to_eur(w52_low,  currency), 2)

        except Exception as e:
            log.warning("  info fetch failed for " + ticker + ": " + str(e))

        out["timestamp"] = datetime.utcnow().isoformat()
       # Attach Morningstar data if pre-fetched (passed in via holding dict)
        if holding.get("star_rating"):
            out["star_rating"]    = holding["star_rating"]
        if holding.get("analyst_rating"):
            out["analyst_rating"] = holding["analyst_rating"]

    except Exception as e:
        out["error"] = "yfinance error for " + ticker + ": " + str(e)

    return out


# -- ANALYST UPGRADES ---------------------------------------------------------
def get_analyst_upgrades(ticker: str, _ignored: str = "", days_back: int = 7,
                         finnhub_symbol: str = "") -> list:
    """
    Fetch broker upgrades/downgrades via yfinance.
    - US tickers: yfinance upgrades_downgrades works reliably.
    - European tickers: Yahoo Finance has no broker data for .PA/.DE/.AS etc.
      Falls back to synthesising a single entry from t.recommendations
      (monthly consensus counts — works for all exchanges).
    """
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()

    is_european = any(ticker.upper().endswith(x) for x in (
        ".PA", ".DE", ".AS", ".MI", ".L", ".ST", ".HE", ".CO",
        ".OL", ".VI", ".SW", ".MC", ".BR", ".LS", ".AT",
    ))

    import logging as _logging
    _yf_log     = _logging.getLogger("yfinance")
    _prev_level = _yf_log.level
    _yf_log.setLevel(_logging.CRITICAL)

    results = []

    # ── 1. yfinance upgrades_downgrades — US tickers only ────────────────────
    if not is_european:
        try:
            t  = yf.Ticker(ticker)
            df = t.upgrades_downgrades
            if df is not None and not df.empty:
                for idx, row in df.iterrows():
                    d = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
                    if d < cutoff:
                        continue
                    fg = str(row.get("FromGrade", "") or "")
                    tg = str(row.get("ToGrade",   "") or "")
                    results.append({
                        "date":       d,
                        "firm":       str(row.get("Firm", "") or ""),
                        "from_grade": fg,
                        "to_grade":   tg,
                        "action":     _grade_action(tg),
                        "source":     "broker",
                    })
        except Exception as e:
            log.warning("  upgrades_downgrades failed for " + ticker + ": " + str(e))
        finally:
            _yf_log.setLevel(_prev_level)

    # ── 2. Fallback: synthesise from recommendations consensus ────────────────
    # recommendations gives monthly Buy/Hold/Sell counts; derive direction
    # by comparing the latest two months. Useful for EU mid-caps where
    # broker-by-broker history is not available on Yahoo.
    if not results:
        try:
            _yf_log.setLevel(_logging.CRITICAL)
            t   = yf.Ticker(ticker)
            rec = t.recommendations
            if rec is not None and not rec.empty:
                # keep last 2 months only
                recent = rec.tail(2)
                rows   = list(recent.itertuples())
                if len(rows) >= 1:
                    last = rows[-1]
                    prev = rows[-2] if len(rows) >= 2 else None
                    # build counts
                    def _counts(r):
                        sb = getattr(r, "strongBuy",  0) or 0
                        b  = getattr(r, "buy",        0) or 0
                        h  = getattr(r, "hold",       0) or 0
                        s  = getattr(r, "sell",       0) or 0
                        ss = getattr(r, "strongSell", 0) or 0
                        return int(sb+b), int(h), int(s+ss)
                    lb, lh, ls = _counts(last)
                    total = lb + lh + ls
                    if total > 0:
                        # Map to a grade label
                        if lb / total >= 0.60:   tg = "Buy"
                        elif ls / total >= 0.40: tg = "Sell"
                        else:                     tg = "Hold"
                        # Compare with previous month to detect direction
                        action = "reit"
                        if prev:
                            pb, ph, ps = _counts(prev)
                            ptotal = pb + ph + ps
                            if ptotal > 0:
                                prev_buy_pct = pb / ptotal
                                curr_buy_pct = lb / total
                                if curr_buy_pct - prev_buy_pct >= 0.10:
                                    action = "up"
                                elif prev_buy_pct - curr_buy_pct >= 0.10:
                                    action = "down"
                        # Date: use index of last row
                        idx = last.Index
                        d = str(idx.date()) if hasattr(idx, "date") else str(idx)[:7]
                        results.append({
                            "date":       d,
                            "firm":       f"{lb} Buy · {lh} Hold · {ls} Sell ({total} analysts)",
                            "from_grade": "",
                            "to_grade":   tg,
                            "action":     action,
                            "source":     "consensus",
                        })
        except Exception as e:
            log.warning("  recommendations fallback failed for " + ticker + ": " + str(e))
        finally:
            _yf_log.setLevel(_prev_level)

    return results[:20]


def _grade_action(tg: str) -> str:
    """Map a grade string to up/down/reit."""
    tl = (tg or "").lower()
    if any(w in tl for w in ["buy", "outperform", "overweight", "strong buy",
                               "accumulate", "add", "positive"]):
        return "up"
    if any(w in tl for w in ["sell", "underperform", "underweight", "strong sell",
                               "reduce", "negative"]):
        return "down"
    return "reit"


def get_analyst_consensus(ticker: str) -> dict:
    """
    Fetch monthly analyst consensus counts (strongBuy/buy/hold/sell/strongSell)
    from yfinance recommendations. Works reliably for both US and European tickers.

    Returns a dict with:
      - months: list of {period, strongBuy, buy, hold, sell, strongSell, total, grade}
      - latest: the most recent month's data
      - trend:  'improving' | 'deteriorating' | 'stable' | 'unknown'
    """
    try:
        t   = yf.Ticker(ticker)
        rec = t.recommendations
        if rec is None or rec.empty:
            return {}

        months = []
        for idx, row in rec.tail(6).iterrows():
            sb = int(row.get("strongBuy",  0) or 0)
            b  = int(row.get("buy",        0) or 0)
            h  = int(row.get("hold",       0) or 0)
            s  = int(row.get("sell",       0) or 0)
            ss = int(row.get("strongSell", 0) or 0)
            total = sb + b + h + s + ss
            if total == 0:
                continue
            buy_pct = (sb + b) / total
            if buy_pct >= 0.60:   grade = "Buy"
            elif (s + ss) / total >= 0.40: grade = "Sell"
            else:                  grade = "Hold"
            period = str(idx.date())[:7] if hasattr(idx, "date") else str(idx)[:7]
            months.append({
                "period":     period,
                "strongBuy":  sb,
                "buy":        b,
                "hold":       h,
                "sell":       s,
                "strongSell": ss,
                "total":      total,
                "buy_pct":    round(buy_pct * 100, 1),
                "grade":      grade,
            })

        if not months:
            return {}

        latest = months[-1]

        # Trend: compare last vs second-last buy_pct
        trend = "unknown"
        if len(months) >= 2:
            delta = months[-1]["buy_pct"] - months[-2]["buy_pct"]
            if delta >= 5:   trend = "improving"
            elif delta <= -5: trend = "deteriorating"
            else:             trend = "stable"

        return {"months": months, "latest": latest, "trend": trend}

    except Exception as e:
        log.warning("  consensus fetch failed for " + ticker + ": " + str(e))
        return {}

def get_morningstar_data(ticker: str, isin: str) -> dict:
    """
    Fetch Morningstar star rating and analyst rating via mstarpy.
    Uses ISIN for reliable lookup across all exchanges.
    Returns dict with star_rating (1-5) and analyst_rating (Gold/Silver/etc)
    """
    if not isin:
        return {}

    try:
        import mstarpy

        # Determine country code from ISIN prefix
        isin_upper  = isin.upper()
        country_map = {
            "US": "us", "DE": "de", "FR": "fr", "GB": "gb",
            "NL": "nl", "SE": "se", "IE": "ie", "CH": "ch",
            "IT": "it", "ES": "es", "BE": "be", "DK": "dk",
            "NO": "no", "FI": "fi", "AT": "at",
        }
        country_code = country_map.get(isin_upper[:2], "us")

        # Try as Fund first (ETFs), then as Stock
        ms_obj  = None
        is_fund = any(ticker.endswith(x) for x in
                      [".DE", ".PA", ".L", ".AS", ".ST", ".MI",
                       ".CO", ".HE", ".OL", ".VI", ".SW", ".MC", ".BR"])

        if is_fund:
            try:
                ms_obj = mstarpy.Funds(term=isin, country=country_code)
            except Exception:
                try:
                    ms_obj = mstarpy.Stock(term=isin, exchange=country_code)
                except Exception:
                    pass
        else:
            try:
                ms_obj = mstarpy.Stock(term=isin, exchange=country_code)
            except Exception:
                try:
                    ms_obj = mstarpy.Funds(term=isin, country=country_code)
                except Exception:
                    pass

        if ms_obj is None:
            return {}

        result = {}

        try:
            sr = ms_obj.starRating()
            if sr:
                result["star_rating"] = int(sr)
        except Exception:
            pass

        try:
            ar = ms_obj.analystRating()
            if ar:
                result["analyst_rating"] = str(ar)
        except Exception:
            pass

        if result:
            log.info("    Morningstar: stars=" + str(result.get("star_rating", "--")) +
                     " rating=" + str(result.get("analyst_rating", "--")))

        return result

    except ImportError:
        log.warning("  mstarpy not installed")
        return {}
    except Exception as e:
        log.warning("  Morningstar fetch failed for " + ticker + ": " + str(e))
        return {}


def get_etf_holdings(ticker: str, max_holdings: int = 25) -> list:
    import math
    import io
    import csv
    import urllib.request

    # ── iShares product ID map ────────────────────────────────────────────────
    ISHARES_PRODUCTS = {
        "EUNK.DE": ("251861", "ishares-core-msci-europe-ucits-etf",       "EUNK"),
        "IS3N.DE": ("264659", "ishares-msci-emerging-markets-imi-ucits-etf", "IS3N"),
        "QDVE.DE": ("280510", "ishares-sp-500-information-technology-sector-ucits-etf", "QDVE"),
        "SEMI.AS": ("319084", "ishares-msci-global-semiconductors-ucits-etf", "SEMI"),
    }
    ISHARES_AJAX = "1506575576011"

    # ── SSGA/SPDR xlsx map ────────────────────────────────────────────────────
    SSGA_PRODUCTS = {
       "SPYY.DE": "https://www.ssga.com/at/en_gb/intermediary/library-content/products/fund-data/etfs/emea/holdings-daily-emea-en-spyy-gy.xlsx",
    }

    def _safe_weight(val) -> float:
        try:
            if isinstance(val, dict):
                val = val.get("raw") or val.get("fmt", "0")
            if isinstance(val, str):
                val = val.strip().rstrip("%").replace(",", "")
                return round(float(val), 2)
            f = float(val)
            if math.isnan(f):
                return 0.0
            return round(f * 100, 2) if f <= 1.0 else round(f, 2)
        except (TypeError, ValueError):
            return 0.0

    def _safe_str(val, fallback: str = "") -> str:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return fallback
        return str(val).strip()

    # ── Source 1: iShares CSV (EUNK, IS3N, QDVE, SEMI) ───────────────────────
    if ticker in ISHARES_PRODUCTS:
        prod_id, slug, file_ticker = ISHARES_PRODUCTS[ticker]
        url = (f"https://www.ishares.com/uk/individual/en/products/"
               f"{prod_id}/{slug}/{ISHARES_AJAX}.ajax"
               f"?fileType=csv&fileName={file_ticker}_holdings&dataType=fund")
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; portfolio-bot/1.0)",
                    "Accept":     "text/csv,*/*",
                    "Referer":    "https://www.ishares.com/",
                }
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            reader  = csv.reader(io.StringIO(raw))
            rows    = list(reader)
            hdr_idx = None
            for i, row in enumerate(rows):
                if row and row[0].strip().lower() in ("ticker", "name") or \
                   any(c.strip().lower() in ("ticker", "weight (%)", "weight(%)") for c in row):
                    hdr_idx = i
                    break
            if hdr_idx is None:
                raise ValueError("Could not find header row in iShares CSV")

            headers = [c.strip().lower() for c in rows[hdr_idx]]

            def _col(*names):
                for n in names:
                    for i, h in enumerate(headers):
                        if n.lower() in h:
                            return i
                return None

            ticker_col = _col("ticker")
            name_col   = _col("name")
            weight_col = _col("weight")

            if weight_col is None:
                raise ValueError(f"No weight column in iShares CSV. Headers: {headers}")

            results = []
            for row in rows[hdr_idx + 1:]:
                if not row or len(row) <= max(filter(lambda x: x is not None,
                                               [ticker_col, name_col, weight_col])):
                    continue
                tk = _safe_str(row[ticker_col]) if ticker_col is not None else "—"
                nm = _safe_str(row[name_col])   if name_col   is not None else "—"
                wt = _safe_weight(row[weight_col])
                if not tk or tk in ("-", "—", "") and not nm:
                    continue
                asset_col = _col("asset class")
                if asset_col is not None and len(row) > asset_col:
                    ac = row[asset_col].strip().lower()
                    if ac in ("cash", "money market", "futures", "options", "fx"):
                        continue
                results.append({
                    "ticker":     tk[:20],
                    "name":       nm[:40],
                    "weight_pct": wt,
                })
                if len(results) >= max_holdings:
                    break

            if results:
                log.info(f"    iShares CSV: {len(results)} holdings for {ticker}")
                return results
            log.warning(f"    iShares CSV returned 0 usable rows for {ticker}")

        except Exception as e:
            log.warning(f"    iShares CSV failed for {ticker}: {e} — falling back to yfinance")

    # ── Source 2: SSGA xlsx (SPYY.DE) ────────────────────────────────────────
    if ticker in SSGA_PRODUCTS:
        try:
            url = SSGA_PRODUCTS[ticker]
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; portfolio-bot/1.0)",
                    "Accept":     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
                    "Referer":    "https://www.ssga.com/",
                }
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                xlsx_bytes = resp.read()

            import openpyxl
            wb  = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
            ws  = wb.active

            all_rows = list(ws.iter_rows(values_only=True))
            wb.close()

            # Log first 6 rows so we can see the exact layout if it fails
            log.info(f"    SSGA xlsx first 6 rows for {ticker}:")
            for i, row in enumerate(all_rows[:6]):
                log.info(f"      row[{i}]: {[str(c)[:30] if c is not None else None for c in row[:8]]}")

            hdr_idx = None
            for i, row in enumerate(all_rows):
                if row is None:
                    continue
                cells = [str(c).strip().lower() if c is not None else "" for c in row]
                # Match any row containing at least 2 of: name, ticker, weight
                if sum(1 for k in ("Security Name", "ISIN", "Percent of Fund") if any(k in c for c in cells)) >= 2:
                    hdr_idx = i
                    break

            if hdr_idx is None:
                raise ValueError("Could not find header row in SSGA xlsx")

            headers = [str(c).strip().lower() if c else "" for c in all_rows[hdr_idx]]

            def _col_idx(*names):
                for n in names:
                    for i, h in enumerate(headers):
                        if n.lower() in h:
                            return i
                return None

            ticker_col = _col_idx("ISIN")
            name_col   = _col_idx("Security Name")
            weight_col = _col_idx("Percent of Fund")

            if weight_col is None:
                raise ValueError(f"No weight column. Headers: {headers}")

            results = []
            for row in all_rows[hdr_idx + 1:]:
                if not row or all(c is None for c in row):
                    continue
                tk = str(row[ticker_col]).strip() if ticker_col is not None and row[ticker_col] else "—"
                nm = str(row[name_col]).strip()   if name_col   is not None and row[name_col]   else "—"
                wt = _safe_weight(row[weight_col]) if row[weight_col] is not None else 0.0
                if tk in ("-", "—", "", "None") and nm in ("-", "—", "", "None"):
                    continue
                if nm.upper() in ("CASH", "USD CASH", "EUR CASH", "FX") or tk.upper() in ("CASH",):
                    continue
                results.append({
                    "ticker":     tk[:20],
                    "name":       nm[:40],
                    "weight_pct": wt,
                })
                if len(results) >= max_holdings:
                    break

            if results:
                log.info(f"    SSGA xlsx: {len(results)} holdings for {ticker}")
                return results
            log.warning(f"    SSGA xlsx returned 0 usable rows for {ticker}")

        except Exception as e:
            log.warning(f"    SSGA xlsx failed for {ticker}: {e} — falling back to yfinance")

    # ── Source 3: yfinance funds_data.top_holdings (fallback / any ticker) ───
    try:
        t  = yf.Ticker(ticker)
        fd = t.funds_data
        if fd is not None:
            th = getattr(fd, "top_holdings", None)
            if th is not None and not (hasattr(th, "empty") and th.empty):
                cols = list(th.columns)
                log.info(f"    top_holdings columns: {cols}")
                if not th.empty:
                    first_row = th.iloc[0]
                    log.info(f"    top_holdings first row: { {c: first_row[c] for c in cols} }")
                results = []
                for idx, row in th.head(max_holdings).iterrows():
                    name = ""
                    for col in ("Name", "holdingName", "name", "security"):
                        try:
                            v = row[col]; name = _safe_str(v)
                            if name: break
                        except (KeyError, TypeError):
                            pass
                    if not name:
                        name = _safe_str(idx)
                    weight_pct = 0.0
                    for col in ("Holding Percent", "holdingPercent", "percent",
                                "weight", "Weight", "pct", "Percent"):
                        try:
                            weight_pct = _safe_weight(row[col])
                            if weight_pct > 0: break
                        except (KeyError, TypeError):
                            pass
                    results.append({
                        "ticker":     _safe_str(idx) or "—",
                        "name":       name[:40],
                        "weight_pct": weight_pct,
                    })
                if results:
                    log.info(f"    ETF holdings (funds_data): {len(results)} for {ticker}")
                    return results
    except Exception as e:
        log.warning(f"    funds_data failed for {ticker}: {e}")

    # ── Source 4: t.info["holdings"] ─────────────────────────────────────────
    try:
        t    = yf.Ticker(ticker)
        info = t.info
        holdings = info.get("holdings") or []
        if holdings:
            results = []
            for h in holdings[:max_holdings]:
                raw_w = h.get("holdingPercent", 0)
                if isinstance(raw_w, dict):
                    raw_w = raw_w.get("raw", 0)
                results.append({
                    "ticker":     _safe_str(h.get("symbol") or h.get("ticker") or "—"),
                    "name":       _safe_str(h.get("holdingName") or h.get("name") or "")[:40],
                    "weight_pct": _safe_weight(raw_w),
                })
            if results:
                log.info(f"    ETF holdings (t.info): {len(results)} for {ticker}")
                return results
    except Exception as e:
        log.warning(f"    t.info holdings failed for {ticker}: {e}")

    log.warning(f"    No ETF holdings data found for {ticker}")
    return []


def get_company_news(ticker: str, _ignored: str = "",
                     days_back: int = 1, max_articles: int = 6,
                     holding_name: str = "") -> list:
    """
    Fetch news from multiple free sources in parallel.

    Sources (all no API key required):
      1. yfinance  .news       — Yahoo Finance JSON news, best ticker-specific coverage
      2. Yahoo Finance RSS     — RSS fallback / extra articles
      3. Google News RSS       — broad coverage, good for European names by company name
      4. Bing News RSS         — different index, catches EU/regional press well
      5. Seeking Alpha RSS     — in-depth analysis pieces, US stocks mainly

    Articles are deduplicated by normalised title, interleaved across sources
    so the final list always represents multiple outlets.
    """
    cutoff       = (date.today() - timedelta(days=days_back)).isoformat()
    holding_name = holding_name or ticker.split(".")[0]

    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    import threading

    is_european = any(ticker.endswith(x) for x in
                      [".DE", ".PA", ".L", ".AS", ".ST", ".MI", ".BR",
                       ".CO", ".HE", ".OL", ".VI", ".SW", ".MC"])

    # ── helpers ──────────────────────────────────────────────────────────────

    def _norm_title(t: str) -> str:
        """Lowercase + strip punctuation for dedup comparison."""
        import re
        return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()

    def _ts_to_date(ts) -> str:
        try:
            return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
        except Exception:
            return ""

    def _parse_rss(raw: bytes, default_source: str) -> list:
        try:
            root  = ET.fromstring(raw)
            items = root.findall(".//item")
        except Exception:
            return []
        results = []
        seen    = set()
        for item in items:
            title = (item.findtext("title") or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            pub = item.findtext("pubDate") or ""
            d = ""
            for _fmt in ("%a, %d %b %Y %H:%M:%S %Z",
                         "%a, %d %b %Y %H:%M:%S %z",
                         "%a, %d %b %Y"):
                try:
                    d = datetime.strptime(pub.strip(), _fmt).strftime("%Y-%m-%d")
                    break
                except Exception:
                    continue
            if d and d < cutoff:
                continue
            # try <source> tag first, fall back to default
            src_el = item.find("source")
            source = (src_el.text if src_el is not None and src_el.text else default_source)
            results.append({
                "title":   title,
                "source":  source,
                "url":     item.findtext("link") or "",
                "date":    d,
                "summary": (item.findtext("description") or "")[:200],
            })
        return results

    def _fetch_rss(url: str, default_source: str) -> list:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; portfolio-bot/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
            return _parse_rss(raw, default_source)
        except Exception as e:
            log.warning("  " + default_source + " RSS failed for " + ticker + ": " + str(e))
            return []

    # ── source fetch functions (run in threads) ───────────────────────────────

    results: dict = {k: [] for k in
                     ["yf", "yahoo_rss", "google", "bing", "seekalpha"]}

    # 1. yfinance .news — best ticker-specific, works for EU stocks
    def _fetch_yf_news():
        try:
            t   = yf.Ticker(ticker)
            raw = t.news or []
            for item in raw:
                ts    = item.get("providerPublishTime") or item.get("publishedAt") or 0
                d     = _ts_to_date(ts)
                if d and d < cutoff:
                    continue
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                results["yf"].append({
                    "title":   title,
                    "source":  item.get("publisher") or "Yahoo Finance",
                    "url":     item.get("link") or item.get("url") or "",
                    "date":    d,
                    "summary": (item.get("summary") or "")[:200],
                })
        except Exception as e:
            log.warning("  yfinance news failed for " + ticker + ": " + str(e))

    # 2. Yahoo Finance RSS (supplement — sometimes has different articles)
    def _fetch_yahoo_rss():
        url = ("https://feeds.finance.yahoo.com/rss/2.0/headline?s="
               + ticker + "&region=US&lang=en-US")
        results["yahoo_rss"].extend(_fetch_rss(url, "Yahoo Finance"))

    # 3. Google News RSS — uses company name, great for European stocks
    def _fetch_google():
        words = holding_name.split()[:3]
        query = urllib.parse.quote(" ".join(words) + " stock")
        url   = ("https://news.google.com/rss/search?q="
                 + query + "&hl=en-US&gl=US&ceid=US:en")
        results["google"].extend(_fetch_rss(url, "Google News"))

    # 4. Bing News RSS — different corpus, catches European/regional press
    def _fetch_bing():
        # For European stocks use the local company name without "stock"
        # suffix — Bing indexes more regional language sources
        words = holding_name.split()[:3]
        query = urllib.parse.quote(" ".join(words) + (" stock" if not is_european else ""))
        url   = ("https://www.bing.com/news/search?q=" + query
                 + "&format=RSS&mkt=en-US")
        results["bing"].extend(_fetch_rss(url, "Bing News"))

    # 5. Seeking Alpha RSS — in-depth articles, mainly US but valuable
    def _fetch_seekalpha():
        if is_european:
            return   # SA has very limited EU stock coverage
        base_ticker = ticker.split(".")[0]
        url  = ("https://seekingalpha.com/api/sa/combined/"
                + base_ticker.upper() + ".xml")
        items = _fetch_rss(url, "Seeking Alpha")
        results["seekalpha"].extend(items)

    threads = [
        threading.Thread(target=_fetch_yf_news),
        threading.Thread(target=_fetch_yahoo_rss),
        threading.Thread(target=_fetch_google),
        threading.Thread(target=_fetch_bing),
        threading.Thread(target=_fetch_seekalpha),
    ]
    for t_ in threads:
        t_.start()
    for t_ in threads:
        t_.join(timeout=12)

    # ── merge: interleave across sources, dedup by normalised title ───────────
    # Priority order: yfinance news first (most relevant), then others
    source_order = ["yf", "google", "bing", "yahoo_rss", "seekalpha"]
    seen_norm  = set()
    merged     = []
    indices    = {k: 0 for k in source_order}

    while len(merged) < max_articles * 3:   # fetch more, trim at end
        added = False
        for src in source_order:
            pool = results[src]
            i    = indices[src]
            if i < len(pool):
                article = pool[i]
                indices[src] += 1
                norm = _norm_title(article["title"])
                if norm and norm not in seen_norm:
                    seen_norm.add(norm)
                    merged.append(article)
                    added = True
        if not added:
            break

    merged.sort(key=lambda x: x.get("date", ""), reverse=True)
    return merged[:max_articles]


# -- CALENDAR -----------------------------------------------------------------
def get_earnings_calendar(ticker: str, _ignored: str = "",
                           from_date: str = "", to_date: str = "") -> list:
    """
    Return next scheduled earnings date for ticker, with EPS and revenue estimates.

    yfinance data sources tried in order of reliability:
      1. t.earnings_dates  — DataFrame with upcoming + recent dates, has 'EPS Estimate'
                             column for future dates. Most reliable for US stocks.
      2. t.calendar        — dict with 'Earnings Date' list; sometimes has EPS/Rev est.
      3. t.info            — 'epsForward' as last-resort EPS fallback
                             'revenueEstimate' key does NOT exist in yfinance info —
                             use 'revenueForecasts' or derive from t.revenue_estimate
      4. t.revenue_estimate — DataFrame with forward revenue by quarter
    """
    try:
        t = yf.Ticker(ticker)

        # ── Step 1: find the earnings date ───────────────────────────────────
        target_date = None
        eps_est     = None
        rev_est     = None

        # Try earnings_dates first — most complete source
        try:
            ed_df = t.earnings_dates
            if ed_df is not None and not ed_df.empty:
                today_str = date.today().isoformat()
                # Filter to future (or very recent — within 7 days past)
                cutoff_past = (date.today() - timedelta(days=7)).isoformat()
                for idx in ed_df.index:
                    d_str = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
                    if d_str < cutoff_past:
                        continue
                    # Check date window
                    if (not from_date or from_date <= d_str) and (not to_date or d_str <= to_date):
                        target_date = d_str
                        # EPS Estimate column
                        row = ed_df.loc[idx]
                        for col in ["EPS Estimate", "epsEstimate", "Eps Estimate"]:
                            val = row.get(col) if hasattr(row, "get") else (
                                row[col] if col in row.index else None
                            )
                            if val is not None and str(val) not in ("nan", "None", ""):
                                try:
                                    eps_est = float(val)
                                except Exception:
                                    pass
                            if eps_est is not None:
                                break
                        break
        except Exception as e:
            log.warning("  earnings_dates failed for " + ticker + ": " + str(e))

        # Fallback to t.calendar for the date
        if target_date is None:
            try:
                cal = t.calendar
                if cal:
                    ed = cal.get("Earnings Date")
                    if ed:
                        d_str = str(ed[0].date()) if hasattr(ed[0], "date") else str(ed[0])[:10]
                        if (not from_date or from_date <= d_str) and (not to_date or d_str <= to_date):
                            target_date = d_str
                            # Try calendar EPS/Rev estimates
                            raw_eps = cal.get("EPS Estimate")
                            raw_rev = cal.get("Revenue Estimate")
                            if raw_eps is not None and str(raw_eps) not in ("nan","None",""):
                                try: eps_est = float(raw_eps)
                                except Exception: pass
                            if raw_rev is not None and str(raw_rev) not in ("nan","None",""):
                                try: rev_est = float(raw_rev)
                                except Exception: pass
            except Exception as e:
                log.warning("  t.calendar failed for " + ticker + ": " + str(e))

        if target_date is None:
            return []

        # ── Step 2: EPS fallback — t.info epsForward ─────────────────────────
        info = {}
        if eps_est is None:
            try:
                info    = t.info or {}
                raw     = info.get("epsForward") or info.get("forwardEps")
                if raw is not None:
                    eps_est = float(raw)
            except Exception:
                pass

        # ── Step 3: Revenue estimate — t.revenue_estimate DataFrame ─────────
        # t.info does NOT have a reliable revenueEstimate key.
        # t.revenue_estimate has rows like "0q" (current quarter), "+1q", "+1y" etc.
        if rev_est is None:
            try:
                re_df = t.revenue_estimate
                if re_df is not None and not re_df.empty:
                    # prefer "0q" (current quarter) over annual
                    for idx_label in ["0q", "+1q", "0y"]:
                        if idx_label in re_df.index:
                            row = re_df.loc[idx_label]
                            for col in ["avg", "Avg", "mean"]:
                                val = row.get(col) if hasattr(row, "get") else (
                                    row[col] if col in row.index else None
                                )
                                if val is not None and str(val) not in ("nan","None",""):
                                    try:
                                        rev_est = float(val)
                                        break
                                    except Exception:
                                        pass
                            if rev_est is not None:
                                break
            except Exception:
                pass

        # Further fallback: quarterly revenue from earnings_estimate DataFrame
        if rev_est is None:
            try:
                ee_df = t.earnings_estimate
                if ee_df is not None and not ee_df.empty:
                    for idx_label in ["0q", "+1q"]:
                        if idx_label in ee_df.index:
                            row = ee_df.loc[idx_label]
                            for col in ["avg", "Avg"]:
                                val = row.get(col) if hasattr(row, "get") else (
                                    row[col] if col in row.index else None
                                )
                                if val is not None and str(val) not in ("nan","None",""):
                                    try:
                                        rev_est = float(val)
                                        break
                                    except Exception:
                                        pass
                            if rev_est is not None:
                                break
            except Exception:
                pass

        # ── Step 4: Quarter derivation ────────────────────────────────────────
        # yfinance info["fiscalYearEnd"] returns a MONTH NAME string e.g. "December"
        # not a numeric prefix — the previous attempt to do int(fy_end[:2]) was wrong.
        quarter = None
        year    = int(target_date[:4])
        try:
            if not info:
                info = t.info or {}
            fy_end_month_name = (info.get("fiscalYearEnd") or "").strip().lower()
            month_map = {
                "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
                "july":7,"august":8,"september":9,"october":10,"november":11,"december":12
            }
            fy_end_month = month_map.get(fy_end_month_name)
            earn_month   = int(target_date[5:7])
            if fy_end_month:
                # Q1 ends 3 months after FY end, Q2 = 6 months, etc.
                offset = (earn_month - fy_end_month) % 12
                quarter = (offset // 3) % 4 + 1
            else:
                # Default: assume Dec fiscal year end (most common)
                quarter = (earn_month - 1) // 3 + 1
        except Exception:
            quarter = (int(target_date[5:7]) - 1) // 3 + 1

        return [{
            "date":         target_date,
            "hour":         "",
            "eps_estimate": eps_est,
            "eps_actual":   None,
            "revenue_est":  rev_est,
            "revenue_act":  None,
            "quarter":      quarter,
            "year":         year,
        }]

    except Exception as e:
        log.warning("  earnings_calendar failed for " + ticker + ": " + str(e))
    return []


def get_dividends(ticker: str, _ignored: str = "",
                  from_date: str = "", to_date: str = "") -> list:
    """
    Return upcoming dividend events within the date window.

    t.dividends only contains historical ex-dates so it will never match a
    future window.  The upcoming ex-date lives in t.calendar under the key
    'Ex-Dividend Date'; the pay date is 'Dividend Date'.  We use that first,
    then fall back to historical data only when no date filter is applied.
    """
    results = []
    try:
        t   = yf.Ticker(ticker)

        # t.calendar internally accesses t.dividends which triggers the
        # 'PriceHistory has no attribute _dividends' yfinance regression
        # for some Euronext tickers. Isolate it.
        cal = {}
        try:
            cal = t.calendar or {}
        except Exception as cal_err:
            log.warning("  t.calendar failed for " + ticker + " (" + str(cal_err) + ")")

        # ── Upcoming ex-date from calendar ───────────────────────────────────
        ex_raw  = cal.get("Ex-Dividend Date") or cal.get("exDividendDate")
        pay_raw = cal.get("Dividend Date")    or cal.get("dividendDate")

        if ex_raw is not None:
            try:
                ex_d  = str(ex_raw.date())  if hasattr(ex_raw,  "date") else str(ex_raw)[:10]
            except Exception:
                ex_d  = str(ex_raw)[:10]
            try:
                pay_d = str(pay_raw.date()) if hasattr(pay_raw, "date") else str(pay_raw)[:10]
            except Exception:
                pay_d = ""

            if (not from_date or from_date <= ex_d) and (not to_date or ex_d <= to_date):
                # Amount: prefer lastDividendValue from info
                amount   = None
                currency = "USD"
                try:
                    info     = t.info
                    amount   = (info.get("lastDividendValue")
                                or info.get("dividendRate"))
                    currency = info.get("currency", "USD")
                    # dividendRate is annual; lastDividendValue is per-payment
                    # if only annual rate is available, divide by typical freq
                    if amount and not info.get("lastDividendValue"):
                        freq = info.get("dividendFrequency") or 4
                        amount = round(amount / freq, 6)
                except Exception:
                    pass
                results.append({
                    "ex_date":     ex_d,
                    "pay_date":    pay_d,
                    "record_date": "",
                    "amount":      float(amount) if amount else None,
                    "currency":    currency,
                    "freq":        "",
                })
                return results

        # ── Fallback: historical dividends (only useful without date filter) ──
        if not from_date and not to_date:
            df = t.dividends
            if df is not None and not df.empty:
                for idx, val in df.items():
                    d = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
                    results.append({
                        "ex_date":     d,
                        "pay_date":    "",
                        "record_date": "",
                        "amount":      float(val),
                        "currency":    "USD",
                        "freq":        "",
                    })

    except Exception as e:
        log.warning("  dividends failed for " + ticker + ": " + str(e))
    return results


def get_stock_splits(ticker: str, _ignored: str = "",
                     from_date: str = "", to_date: str = "") -> list:
    try:
        t  = yf.Ticker(ticker)
        df = t.splits
        if df is None or df.empty:
            return []
        results = []
        for idx, val in df.items():
            d = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
            if (not from_date or from_date <= d) and (not to_date or d <= to_date):
                results.append({"date": d, "ratio": str(val) + ":1"})
        return results
    except Exception:
        return []


# -- kept for any legacy import -----------------------------------------------
def to_finnhub_symbol(ticker: str) -> str:
    return ticker


# -- EMAIL --------------------------------------------------------------------
def send_email(subject: str, html: str, cfg: dict) -> bool:
    a = cfg["alerts"]
    if not a.get("email_enabled") or not a.get("email_from") or not a.get("email_password"):
        log.info("  Email skipped (not configured)")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = a["email_from"]
        msg["To"]      = a["email_to"]
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.agentmail.to", 465, timeout=20) as s:
            s.login(a["email_from"], a["email_password"])
            s.send_message(msg)
        log.info("  Sent: " + subject)
        return True
    except Exception as e:
        log.error("  Email failed: " + str(e))
        return False


# -- ALERT LOG ----------------------------------------------------------------
def append_alert(alert_type: str, ticker: str, message: str):
    alerts = load_json(ALERTS_F, [])
    alerts.insert(0, {
        "ts":      datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "type":    alert_type,
        "ticker":  ticker,
        "message": message,
    })
    save_json(ALERTS_F, alerts[:500])


# -- EMAIL HTML TEMPLATES -----------------------------------------------------
_BASE = (
    "font-family:'Arial',sans-serif;background:#161b22;"
    "color:#f0f2f5;padding:32px;max-width:680px;margin:auto;border-radius:12px"
)


def _TH(s):
    return (
        "<th style='padding:8px 12px;text-align:left;background:#87CEFB;"
        "color:#0a0a0a;font-size:10px;text-transform:uppercase;"
        "letter-spacing:1px'>" + s + "</th>"
    )


def _td(v, x=""):
    return (
        "<td style='padding:8px 12px;border-bottom:1px solid #21293a;"
        "background:#87CEFB;color:#0a0a0a;" + x + "'>"
        + str(v) + "</td>"
    )


def _holding_row(s: dict) -> str:
    chg          = s.get("change_pct") or 0
    price_native = s.get("price_native") or 0
    prev_close   = s.get("prev_close")   or 0
    market_closed = (abs(chg) < 0.001 and price_native > 0
                     and abs(price_native - prev_close) < 0.001)
    color = "#7d8fa8" if market_closed else ("#1a7a3a" if chg >= 0 else "#c0392b")
    arrow = "+" if chg >= 0 else "-"

    # Analyst cell
    rec      = (s.get("recommendation") or "").replace("_", " ")
    ms_stars = s.get("star_rating")
    ms_ar    = s.get("analyst_rating") or ""
    ar_color = (
        "#b8860b" if ms_ar == "Gold"
        else "#707070" if ms_ar == "Silver"
        else "#8B4513" if ms_ar == "Bronze"
        else "#c0392b" if ms_ar == "Negative"
        else "#555555"
    )

    if ms_stars:
        stars_str = ("★" * ms_stars) + ("☆" * (5 - ms_stars))
        if ms_ar:
            analyst_html = (
                "<span style='color:#b8860b'>" + stars_str + "</span>"
                " <span style='color:" + ar_color + ";font-size:10px'>" + ms_ar + "</span>"
            )
        else:
            analyst_html = "<span style='color:#b8860b'>" + stars_str + "</span>"
    elif rec:
        rc           = "#1a7a3a" if "buy" in rec else "#c0392b" if "sell" in rec else "#b8860b"
        analyst_html = (
            "<span style='color:" + rc + ";font-size:10px;text-transform:uppercase'>"
            + rec + "</span>"
        )
    else:
        analyst_html = "<span style='color:#555555'>--</span>"

    p_raw  = s.get("price_eur")
    v_raw  = s.get("value_eur")
    shares = s.get("shares") or 0
    p_str  = "{:.2f}".format(float(p_raw)) if p_raw not in (None, "", "--") else "--"
    v_str  = "{:.2f}".format(float(v_raw)) if v_raw not in (None, "", "--") else "--"
    if v_str == "--" and p_str != "--" and shares:
        v_str = "{:.2f}".format(float(p_str) * float(shares))

    closed_badge = (
        "<span style='color:#555555;font-size:9px'> mkt closed</span>"
        if market_closed else ""
    )
    chg_cell = (
        "<span style='color:" + color + ";font-weight:600'>"
        + arrow + " " + "{:.2f}".format(abs(chg)) + "%"
        + "</span>" + closed_badge
    )

    return (
        "<tr>"
        + _td(s.get("ticker", ""),        "color:#06402B;font-weight:700")
        + _td((s.get("name") or "")[:26], "color:#06402B;font-weight:600")
        + _td(("EUR " + p_str) if p_str != "--" else "--", "color:#0a0a0a")
        + _td(chg_cell)
        + _td(str(shares) if shares else "--", "color:#0a0a0a")
        + _td(("EUR " + v_str) if v_str != "--" else "--", "color:#0a0a0a;font-weight:700")
        + _td(analyst_html)
        + "</tr>"
    )

def _table(rows: str) -> str:
    heads = "".join(_TH(h) for h in
                    ["Ticker", "Name", "Price EUR", "Day Chg", "Shares", "Value EUR", "Analyst"])
    return (
        "<table style='width:100%;border-collapse:collapse;"
        "background:#87CEFB;border-radius:8px;overflow:hidden'>"
        "<thead><tr>" + heads + "</tr></thead><tbody>" + rows + "</tbody></table>"
    )


def digest_html(snapshot: dict, label: str) -> str:
    total    = snapshot.get("total_eur", 0)
    stk_rows = "".join(_holding_row(s) for s in snapshot.get("stocks", []) if "error" not in s)
    etf_rows = "".join(_holding_row(e) for e in snapshot.get("etfs",   []) if "error" not in e)
    now      = datetime.utcnow().strftime("%A, %d %B %Y - %H:%M UTC")
    return (
        "<div style='" + _BASE + "'>"
        "<div style='font-size:10px;color:#7d8fa8;text-transform:uppercase;"
        "letter-spacing:2px;margin-bottom:6px'>Portfolio Digest</div>"
        "<h1 style='font-size:20px;color:#4f9ef8;margin:0 0 4px'>Portfolio Digest - " + label + "</h1>"
        "<p style='color:#7d8fa8;margin:0 0 20px'>" + now + "</p>"
        "<p style='font-size:24px;color:#52d68a;margin:0 0 24px'>Total: <strong>EUR "
        + "{:,.2f}".format(total) + "</strong></p>"
        "<h2 style='font-size:14px;color:#f0f2f5;margin:0 0 10px'>Stocks</h2>"
        + _table(stk_rows)
        + "<h2 style='font-size:14px;color:#f0f2f5;margin:24px 0 10px'>ETFs</h2>"
        + _table(etf_rows)
        + "<p style='color:#4a5568;font-size:10px;margin-top:24px'>"
        "Portfolio Intelligence - GitHub Actions - Yahoo Finance</p>"
        "</div>"
    )


def movement_html(ticker: str, name: str, price_now: float,
                  price_prev: float, move_pct: float) -> str:
    color = "#52d68a" if move_pct > 0 else "#f56565"
    arrow = "UP" if move_pct > 0 else "DOWN"
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return (
        "<div style='" + _BASE + "'>"
        "<h1 style='font-size:26px;color:" + color + ";margin:0 0 8px'>"
        + arrow + " " + ticker + "</h1>"
        "<p style='color:#7d8fa8;margin:0 0 20px'>" + name + "</p>"
        "<table style='width:100%;border-collapse:collapse;"
        "background:#1c2330;border-radius:8px;overflow:hidden'>"
        "<tr><td style='padding:12px 16px;color:#7d8fa8'>Previous close</td>"
        "<td style='padding:12px 16px;font-weight:600'>EUR "
        + "{:.2f}".format(price_prev) + "</td></tr>"
        "<tr><td style='padding:12px 16px;color:#7d8fa8'>Current price</td>"
        "<td style='padding:12px 16px;font-weight:600;color:" + color + "'>EUR "
        + "{:.2f}".format(price_now) + "</td></tr>"
        "<tr><td style='padding:12px 16px;color:#7d8fa8'>Change</td>"
        "<td style='padding:12px 16px;font-size:22px;font-weight:700;color:" + color + "'>"
        + arrow + " " + "{:.2f}".format(abs(move_pct)) + "%</td></tr>"
        "</table>"
        "<p style='color:#4a5568;font-size:10px;margin-top:20px'>" + now + "</p>"
        "</div>"
    )


def rating_change_html(ticker: str, name: str, changes: list) -> str:
    def _row(c):
        to_g   = c.get("to_grade", "")
        tl     = to_g.lower()
        col    = (
            "#52d68a" if any(w in tl for w in ["buy", "outperform", "overweight", "positive"])
            else "#f56565" if any(w in tl for w in ["sell", "underperform", "underweight", "negative"])
            else "#f6ad55"
        )
        action = c.get("action", "").lower()
        badge_map = {
            "up":   "<span style='color:#52d68a;font-size:10px'>UPGRADE</span>",
            "down": "<span style='color:#f56565;font-size:10px'>DOWNGRADE</span>",
            "init": "<span style='color:#4f9ef8;font-size:10px'>INITIATION</span>",
            "reit": "<span style='color:#7d8fa8;font-size:10px'>REITERATE</span>",
        }
        bd = "1px solid #21293a"
        return (
            "<tr>"
            "<td style='padding:9px 12px;border-bottom:" + bd + ";color:#7d8fa8'>"
            + c.get("date", "") + "</td>"
            "<td style='padding:9px 12px;border-bottom:" + bd + ";font-weight:600'>"
            + c.get("firm", "") + "</td>"
            "<td style='padding:9px 12px;border-bottom:" + bd + ";"
            "color:#7d8fa8;text-decoration:line-through'>"
            + (c.get("from_grade") or "--") + "</td>"
            "<td style='padding:9px 12px;border-bottom:" + bd + "'>-></td>"
            "<td style='padding:9px 12px;border-bottom:" + bd + ";color:" + col + ";"
            "font-weight:700'>" + to_g + "</td>"
            "<td style='padding:9px 12px;border-bottom:" + bd + "'>"
            + badge_map.get(action, "") + "</td>"
            "</tr>"
        )

    rows  = "".join(_row(c) for c in changes)
    heads = "".join(_TH(h) for h in ["Date", "Firm", "From", "", "To", "Action"])
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return (
        "<div style='" + _BASE + "'>"
        "<h1 style='font-size:24px;color:#b794f4;margin:0 0 6px'>" + ticker + "</h1>"
        "<p style='color:#7d8fa8;margin:0 0 24px'>" + name + "</p>"
        "<table style='width:100%;border-collapse:collapse;"
        "background:#1c2330;border-radius:8px;overflow:hidden'>"
        "<thead><tr>" + heads + "</tr></thead><tbody>" + rows + "</tbody></table>"
        "<p style='color:#4a5568;font-size:10px;margin-top:20px'>" + now + "</p>"
        "</div>"
    )


def news_digest_html(holdings_with_news: list, run_label: str) -> str:
    now = datetime.utcnow().strftime("%A, %d %B %Y - %H:%M UTC")

    def _section(h):
        articles = h.get("news", [])
        if not articles:
            return ""
        rows = ""
        for a in articles:
            src   = a.get("source", "")
            d     = a.get("date", "")
            summ  = (a.get("summary") or "")[:160]
            if summ and not summ.endswith((".", "...")):
                summ += "..."
            url   = a.get("url", "#")
            title = a.get("title", "")
            rows += (
                "<tr><td style='padding:12px 14px;border-bottom:1px solid #21293a;"
                "vertical-align:top'>"
                "<a href='" + url + "' style='color:#4f9ef8;text-decoration:none;"
                "font-weight:600;font-size:12.5px;display:block;margin-bottom:5px'>"
                + title + "</a>"
                "<span style='color:#52d68a;font-size:11px'>" + src + "</span>"
                "<span style='color:#7d8fa8;font-size:11px'>"
                + (" - " + d if d else "") + "</span>"
                + ("<div style='color:#7d8fa8;font-size:11px;margin-top:4px'>"
                   + summ + "</div>" if summ else "")
                + "</td></tr>"
            )
        return (
            "<div style='margin-bottom:20px'>"
            "<span style='color:#4f9ef8;font-weight:600'>" + h["ticker"] + "</span>"
            " <span style='color:#7d8fa8;font-size:11px'>" + h.get("name", "") + "</span>"
            "<table style='width:100%;border-collapse:collapse;background:#1c2330;"
            "border-radius:8px;overflow:hidden;margin-top:8px'>"
            "<tbody>" + rows + "</tbody></table></div>"
        )

    sections = "".join(_section(h) for h in holdings_with_news)
    total    = sum(len(h.get("news", [])) for h in holdings_with_news)
    return (
        "<div style='" + _BASE + "'>"
        "<h1 style='font-size:20px;color:#52d68a;margin:0 0 4px'>"
        "News Digest - " + run_label + "</h1>"
        "<p style='color:#7d8fa8;margin:0 0 6px'>" + now + "</p>"
        "<p style='color:#7d8fa8;font-size:11px;margin:0 0 24px'>"
        + str(total) + " article(s) across "
        + str(len(holdings_with_news)) + " holding(s)</p>"
        + sections
        + "<p style='color:#4a5568;font-size:10px;margin-top:16px'>"
        "Portfolio Intelligence - GitHub Actions</p>"
        "</div>"
    )


def saturday_summary_html(snapshot: dict, intel_data: dict,
                           week_movements: list) -> str:
    now        = datetime.utcnow().strftime("%A, %d %B %Y - %H:%M UTC")
    total_eur  = snapshot.get("total_eur", 0)
    week_start = snapshot.get("week_start_eur")
    week_chg   = ((total_eur - week_start) / week_start * 100) if week_start else None
    chg_color  = "#52d68a" if (week_chg or 0) >= 0 else "#f56565"

    week_chg_html = ""
    if week_chg is not None:
        week_chg_html = (
            "<div><div style='font-size:10px;color:#7d8fa8;text-transform:uppercase;"
            "letter-spacing:1px;margin-bottom:6px'>Week Change</div>"
            "<div style='font-size:22px;color:" + chg_color + ";font-weight:700'>"
            + ("+" if week_chg >= 0 else "") + "{:.2f}".format(week_chg) + "%</div></div>"
        )

    week_block = (
        "<div style='background:#1c2330;border-radius:10px;padding:20px 24px;"
        "margin-bottom:24px;display:flex;justify-content:space-between;"
        "align-items:center;flex-wrap:wrap;gap:12px'>"
        "<div><div style='font-size:10px;color:#7d8fa8;text-transform:uppercase;"
        "letter-spacing:1px;margin-bottom:6px'>Portfolio Value</div>"
        "<div style='font-size:28px;color:#52d68a;font-weight:700'>EUR "
        + "{:,.2f}".format(total_eur) + "</div></div>"
        + week_chg_html + "</div>"
    )

    # -- Holdings table with week change --
    def _week_chg_for(ticker: str) -> float:
        for m in week_movements:
            if m.get("ticker") == ticker:
                return m.get("move_pct", 0)
        return 0.0

    def _holding_row_weekly(s: dict) -> str:
        ticker   = s.get("ticker", "")
        name     = (s.get("name") or "")[:26]
        p_raw    = s.get("price_eur")
        v_raw    = s.get("value_eur")
        shares   = s.get("shares") or 0
        p_str    = "{:.2f}".format(float(p_raw)) if p_raw not in (None, "", "--") else "--"
        v_str    = "{:.2f}".format(float(v_raw)) if v_raw not in (None, "", "--") else "--"
        if v_str == "--" and p_str != "--" and shares:
            v_str = "{:.2f}".format(float(p_str) * float(shares))

        wchg     = _week_chg_for(ticker)
        wcolor   = "#1a7a3a" if wchg >= 0 else "#c0392b"
        warrow   = "+" if wchg >= 0 else "-"
        wchg_cell = (
            "<span style='color:" + wcolor + ";font-weight:600'>"
            + warrow + " " + "{:.2f}".format(abs(wchg)) + "%"
            + "</span>"
        )

        rec      = (s.get("recommendation") or "").replace("_", " ")
        ms_stars = s.get("star_rating")
        ms_ar    = s.get("analyst_rating") or ""
        ar_color = (
            "#b8860b" if ms_ar == "Gold"
            else "#707070" if ms_ar == "Silver"
            else "#8B4513" if ms_ar == "Bronze"
            else "#c0392b" if ms_ar == "Negative"
            else "#555555"
        )
        if ms_stars:
            stars_str    = ("★" * ms_stars) + ("☆" * (5 - ms_stars))
            analyst_html = (
                "<span style='color:#b8860b'>" + stars_str + "</span>"
                + (" <span style='color:" + ar_color + ";font-size:10px'>" + ms_ar + "</span>" if ms_ar else "")
            )
        elif rec:
            rc           = "#1a7a3a" if "buy" in rec else "#c0392b" if "sell" in rec else "#b8860b"
            analyst_html = "<span style='color:" + rc + ";font-size:10px;text-transform:uppercase'>" + rec + "</span>"
        else:
            analyst_html = "<span style='color:#555555'>--</span>"

        bd = "border-bottom:1px solid #21293a;background:#87CEFB;color:#0a0a0a"
        return (
            "<tr>"
            "<td style='padding:8px 12px;" + bd + ";color:#06402B;font-weight:700'>" + ticker + "</td>"
            "<td style='padding:8px 12px;" + bd + ";color:#06402B;font-weight:600'>" + name + "</td>"
            "<td style='padding:8px 12px;" + bd + "'>" + (("EUR " + p_str) if p_str != "--" else "--") + "</td>"
            "<td style='padding:8px 12px;" + bd + "'>" + wchg_cell + "</td>"
            "<td style='padding:8px 12px;" + bd + "'>" + (str(shares) if shares else "--") + "</td>"
            "<td style='padding:8px 12px;" + bd + ";font-weight:700'>" + (("EUR " + v_str) if v_str != "--" else "--") + "</td>"
            "<td style='padding:8px 12px;" + bd + "'>" + analyst_html + "</td>"
            "</tr>"
        )

    def _holdings_table(items: list) -> str:
        heads = "".join(
            "<th style='padding:8px 12px;text-align:left;background:#87CEFB;"
            "color:#0a0a0a;font-size:10px;text-transform:uppercase;letter-spacing:1px'>"
            + h + "</th>"
            for h in ["Ticker", "Name", "Price EUR", "Week Chg", "Shares", "Value EUR", "Analyst"]
        )
        rows = "".join(
            _holding_row_weekly(s)
            for s in items
            if "error" not in s
        )
        return (
            "<table style='width:100%;border-collapse:collapse;"
            "background:#87CEFB;border-radius:8px;overflow:hidden'>"
            "<thead><tr>" + heads + "</tr></thead><tbody>" + rows + "</tbody></table>"
        )

    stocks_table = (
        "<h2 style='font-size:14px;color:#f0f2f5;margin:0 0 10px'>Stocks</h2>"
        + _holdings_table(snapshot.get("stocks", []))
        + "<h2 style='font-size:14px;color:#f0f2f5;margin:24px 0 10px'>ETFs</h2>"
        + _holdings_table(snapshot.get("etfs", []))
    )

    # -- Top movers block --
    movers_block = ""
    if week_movements:
        top  = sorted(week_movements, key=lambda x: abs(x.get("move_pct", 0)), reverse=True)[:8]
        rows = ""
        for m in top:
            mp  = m.get("move_pct", 0)
            col = "#52d68a" if mp >= 0 else "#f56565"
            rows += (
                "<tr>"
                "<td style='padding:9px 14px;border-bottom:1px solid #21293a;"
                "color:#4f9ef8;font-weight:600'>" + m.get("ticker", "") + "</td>"
                "<td style='padding:9px 14px;border-bottom:1px solid #21293a;"
                "color:#7d8fa8'>" + m.get("name", "")[:24] + "</td>"
                "<td style='padding:9px 14px;border-bottom:1px solid #21293a'>EUR "
                + "{:.2f}".format(m.get("from_eur", 0)) + "</td>"
                "<td style='padding:9px 14px;border-bottom:1px solid #21293a'>EUR "
                + "{:.2f}".format(m.get("to_eur", 0)) + "</td>"
                "<td style='padding:9px 14px;border-bottom:1px solid #21293a;"
                "color:" + col + ";font-weight:700'>"
                + ("+" if mp >= 0 else "") + "{:.2f}".format(mp) + "%</td>"
                "</tr>"
            )
        heads = "".join(
            "<th style='padding:8px 14px;text-align:left;background:#1c2330;"
            "color:#7d8fa8;font-size:10px;text-transform:uppercase;letter-spacing:1px'>"
            + h + "</th>"
            for h in ["Ticker", "Name", "Mon Open", "Fri Close", "Week Chg"]
        )
        movers_block = (
            "<h2 style='font-size:14px;color:#f0f2f5;margin:24px 0 10px'>"
            "Top Movers This Week</h2>"
            "<table style='width:100%;border-collapse:collapse;background:#1c2330;"
            "border-radius:8px;overflow:hidden;margin-bottom:24px'>"
            "<thead><tr>" + heads + "</tr></thead><tbody>" + rows + "</tbody></table>"
        )

    # -- Rating changes block --
    cutoff      = (datetime.utcnow() - timedelta(days=6)).strftime("%Y-%m-%d")
    all_changes = []
    for h in (intel_data.get("holdings") or []):
        for r in (h.get("ratings") or []):
            if (r.get("date", "") >= cutoff
                    and r.get("to_grade")
                    and (r.get("from_grade", "") or "").lower() != r.get("to_grade", "").lower()):
                all_changes.append({**r, "ticker": h["ticker"], "name": h.get("name", "")})
    all_changes.sort(key=lambda x: x.get("date", ""), reverse=True)

    ratings_block = ""
    if all_changes:
        def _rcrow(c):
            to_g  = c.get("to_grade", "")
            col   = (
                "#52d68a" if any(w in to_g.lower() for w in ["buy", "outperform", "overweight"])
                else "#f56565" if any(w in to_g.lower() for w in ["sell", "underperform", "underweight"])
                else "#f6ad55"
            )
            act   = c.get("action", "").lower()
            a_lbl = {"up": "UPGRADE", "down": "DOWNGRADE", "init": "INIT", "reit": "--"}.get(act, act)
            a_col = {"up": "#52d68a", "down": "#f56565", "init": "#4f9ef8"}.get(act, "#7d8fa8")
            bd    = "1px solid #21293a"
            return (
                "<tr>"
                "<td style='padding:8px 12px;border-bottom:" + bd + ";"
                "color:#4f9ef8;font-weight:600'>" + c.get("ticker", "") + "</td>"
                "<td style='padding:8px 12px;border-bottom:" + bd + ";"
                "color:#7d8fa8'>" + c.get("date", "") + "</td>"
                "<td style='padding:8px 12px;border-bottom:" + bd + "'>"
                + c.get("firm", "") + "</td>"
                "<td style='padding:8px 12px;border-bottom:" + bd + ";"
                "color:#7d8fa8;text-decoration:line-through'>"
                + (c.get("from_grade") or "--") + "</td>"
                "<td style='padding:8px 12px;border-bottom:" + bd + "'>-></td>"
                "<td style='padding:8px 12px;border-bottom:" + bd + ";color:" + col + ";"
                "font-weight:700'>" + to_g + "</td>"
                "<td style='padding:8px 12px;border-bottom:" + bd + ";color:" + a_col + ";"
                "font-size:10px'>" + a_lbl + "</td>"
                "</tr>"
            )
        rc_heads = "".join(
            "<th style='padding:8px 12px;text-align:left;background:#1c2330;"
            "color:#7d8fa8;font-size:10px;text-transform:uppercase;letter-spacing:1px'>"
            + h + "</th>"
            for h in ["Ticker", "Date", "Firm", "From", "", "To", "Action"]
        )
        ratings_block = (
            "<h2 style='font-size:14px;color:#f0f2f5;margin:24px 0 10px'>"
            "Rating Changes This Week</h2>"
            "<table style='width:100%;border-collapse:collapse;background:#1c2330;"
            "border-radius:8px;overflow:hidden;margin-bottom:24px'>"
            "<thead><tr>" + rc_heads + "</tr></thead>"
            "<tbody>" + "".join(_rcrow(c) for c in all_changes) + "</tbody></table>"
        )

    # -- News block --
    news_sections = ""
    for h in (intel_data.get("holdings") or []):
        articles = [a for a in (h.get("news") or []) if a.get("date", "") >= cutoff]
        if not articles:
            continue
        rows = ""
        for a in articles[:4]:
            url   = a.get("url", "#")
            title = a.get("title", "")
            src   = a.get("source", "")
            dt    = a.get("date", "")
            summ  = (a.get("summary") or "")[:140]
            rows += (
                "<tr><td style='padding:11px 14px;border-bottom:1px solid #21293a;"
                "vertical-align:top'>"
                "<a href='" + url + "' style='color:#4f9ef8;text-decoration:none;"
                "font-weight:600;font-size:12px;display:block;margin-bottom:4px'>"
                + title + "</a>"
                "<span style='color:#52d68a;font-size:10px'>" + src + "</span>"
                "<span style='color:#7d8fa8;font-size:10px'>"
                + (" - " + dt if dt else "") + "</span>"
                + ("<div style='color:#7d8fa8;font-size:11px;margin-top:3px'>"
                   + summ + "...</div>" if summ else "")
                + "</td></tr>"
            )
        news_sections += (
            "<div style='margin-bottom:18px'>"
            "<span style='color:#4f9ef8;font-weight:600'>" + h.get("ticker", "") + "</span>"
            "<span style='color:#7d8fa8;font-size:11px;margin-left:8px'>"
            + h.get("name", "") + "</span>"
            "<table style='width:100%;border-collapse:collapse;background:#1c2330;"
            "border-radius:8px;overflow:hidden;margin-top:8px'>"
            "<tbody>" + rows + "</tbody></table></div>"
        )
    if news_sections:
        news_sections = (
            "<h2 style='font-size:14px;color:#f0f2f5;margin:24px 0 12px'>"
            "News This Week</h2>" + news_sections
        )

    return (
        "<div style='" + _BASE + "'>"
        "<h1 style='font-size:20px;color:#f6ad55;margin:0 0 4px'>Weekly Summary</h1>"
        "<p style='color:#7d8fa8;margin:0 0 24px'>" + now + "</p>"
        + week_block
        + stocks_table
        + movers_block
        + ratings_block
        + news_sections
        + "<p style='color:#4a5568;font-size:10px;margin-top:24px'>"
        "Portfolio Intelligence - GitHub Actions</p>"
        "</div>"
    )


def next_week_calendar_html(calendar: dict, next_mon: str, next_fri: str) -> str:
    def _TH2(s):
        return (
            "<th style='padding:8px 12px;text-align:left;background:#87CEFB;"
            "color:#0a0a0a;font-size:10px;text-transform:uppercase;letter-spacing:1px'>"
            + s + "</th>"
        )

    def _td2(v, x=""):
        return (
            "<td style='padding:9px 12px;border-bottom:1px solid #21293a;"
            "background:#87CEFB;color:#0a0a0a;" + x + "'>"
            + str(v) + "</td>"
        )

    def _section(title, color, rows_html, cols):
        heads = "".join(_TH2(c) for c in cols)
        return (
            "<h2 style='font-size:14px;color:" + color + ";margin:0 0 10px'>"
            + title + "</h2>"
            "<table style='width:100%;border-collapse:collapse;background:#1c2330;"
            "border-radius:8px;overflow:hidden;margin-bottom:24px'>"
            "<thead><tr>" + heads + "</tr></thead><tbody>" + rows_html + "</tbody></table>"
        )

    earnings_block = ""
    if calendar.get("earnings"):
        rows = ""
        for e in calendar["earnings"]:
            eps = ("$" + "{:.2f}".format(e["eps_estimate"])) if e.get("eps_estimate") is not None else "--"
            rev = ("$" + "{:.1f}".format(e["revenue_est"] / 1e9) + "B") if (e.get("revenue_est") and e["revenue_est"] > 1e6) else "--"
            rows += (
                "<tr>"
                + _td2(e.get("date", ""),      "color:#7d8fa8")
                + _td2(e.get("ticker", ""),     "color:#4f9ef8;font-weight:600")
                + _td2(e.get("name", "")[:22],  "color:#7d8fa8")
                + _td2(eps,                      "color:#f6ad55")
                + _td2(rev,                      "color:#7d8fa8")
                + "</tr>"
            )
        earnings_block = _section(
            "Earnings Reports Next Week", "#f6ad55", rows,
            ["Date", "Ticker", "Company", "EPS Est.", "Rev Est."]
        )

    dividends_block = ""
    if calendar.get("dividends"):
        rows = ""
        for d in calendar["dividends"]:
            amt = ((d.get("currency", "") + " " + "{:.4f}".format(d["amount"]))
                   if d.get("amount") is not None else "--")
            rows += (
                "<tr>"
                + _td2(d.get("ex_date", ""),   "color:#7d8fa8")
                + _td2(d.get("ticker", ""),     "color:#4f9ef8;font-weight:600")
                + _td2(d.get("name", "")[:22],  "color:#7d8fa8")
                + _td2(amt,                      "color:#52d68a")
                + "</tr>"
            )
        dividends_block = _section(
            "Ex-Dividend Dates Next Week", "#52d68a", rows,
            ["Ex-Date", "Ticker", "Company", "Amount"]
        )

    splits_block = ""
    if calendar.get("splits"):
        rows = ""
        for s in calendar["splits"]:
            rows += (
                "<tr>"
                + _td2(s.get("date", ""),      "color:#7d8fa8")
                + _td2(s.get("ticker", ""),     "color:#4f9ef8;font-weight:600")
                + _td2(s.get("name", "")[:22],  "color:#7d8fa8")
                + _td2(s.get("ratio", "--"),     "color:#b794f4;font-weight:600")
                + "</tr>"
            )
        splits_block = _section(
            "Stock Splits Next Week", "#b794f4", rows,
            ["Date", "Ticker", "Company", "Ratio"]
        )

    if not earnings_block and not dividends_block and not splits_block:
        body = (
            "<div style='background:#1c2330;border-radius:8px;padding:18px 20px;"
            "color:#7d8fa8;font-size:12px;margin-bottom:24px'>"
            "No earnings, dividends, or splits scheduled for your holdings "
            "next week (" + next_mon + " - " + next_fri + ").</div>"
        )
    else:
        body = earnings_block + dividends_block + splits_block

    return (
        "<h2 style='font-size:15px;color:#f0f2f5;margin:0 0 4px'>"
        "Next Week's Important Dates</h2>"
        "<p style='color:#7d8fa8;font-size:11px;margin:0 0 16px'>"
        + next_mon + " - " + next_fri + "</p>"
        + body
    )

def get_perplexity_sentiment(ticker: str, name: str) -> dict:
    """
    Fetch trading sentiment for a stock via Perplexity API.
    Returns dict with sentiment, rationale, lower_bound, upper_bound, contra.
    """
    import urllib.request
    import json as _json

    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        log.warning("  PERPLEXITY_API_KEY not set")
        return {}

    prompt = (
        "Role: You are a Senior Quantitative Financial Analyst with expertise "
        "in European and US equity markets.\n\n"
        "Task: Analyze the current market position, sentiment, and probable price "
        "range for " + ticker + " (" + name + ").\n\n"
        "Instructions:\n"
        "1. NEWS & FUNDAMENTALS (last 7 days): Search for recent news from Reuters, "
        "Bloomberg, and where relevant German/European sources (Handelsblatt, "
        "Börse Frankfurt, Der Aktionär). Identify earnings, guidance changes, "
        "analyst upgrades/downgrades, M&A activity, or macro events.\n"
        "2. SOCIAL SENTIMENT: Check Reddit (r/stocks, r/investing, r/wallstreetbets, "
        "r/mauerstrassenwetten). Identify dominant retail sentiment.\n"
        "3. TECHNICAL CONTEXT: Identify support and resistance levels. Estimate a "
        "70% probability weekly price range. All prices must be in EUR.\n"
        "4. RISK ASSESSMENT: Identify the single biggest downside risk this week.\n\n"
        "Format your response EXACTLY as follows, no extra text before or after:\n\n"
        "SENTIMENT: [Bullish / Neutral / Bearish]\n\n"
        "RATIONALE: [Maximum 2 sentences. Be specific — cite the actual event or "
        "data point driving sentiment.]\n\n"
        "WEEKLY RANGE (70% Probability):\n"
        "  Lower Bound: €[Price] — [Short reason]\n"
        "  Upper Bound: €[Price] — [Short reason]\n\n"
        "CONTRA-VIEW: [1 sentence on the single biggest risk that could invalidate "
        "this outlook this week.]"
    )

    payload = _json.dumps({
        "model":                 "sonar",
        "messages": [
            {
                "role":    "system",
                "content": (
                    "You are a financial analyst. Be concise and factual. "
                    "Always base your answer on the most recent available information. "
                    "Never add introductory text. Reply only in the exact format requested."
                )
            },
            {
                "role":    "user",
                "content": prompt
            }
        ],
        "max_tokens":            350,
        "temperature":           0.2,
        "search_recency_filter": "week",
        "return_citations":      False,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://api.perplexity.ai/chat/completions",
            data=payload,
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type":  "application/json",
                "Accept":        "application/json",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read().decode("utf-8"))

        text = data["choices"][0]["message"]["content"].strip()
        log.info("  Perplexity raw (" + ticker + "): " + text[:120])

        # --- Parse response ---
        sentiment   = "Neutral"
        rationale   = ""
        lower_bound = ""
        upper_bound = ""
        contra      = ""
        current_section = None

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            lu = line.upper()

            if lu.startswith("SENTIMENT:"):
                val = line.split(":", 1)[1].strip().capitalize()
                if val in ("Bullish", "Bearish", "Neutral"):
                    sentiment = val
                current_section = None

            elif lu.startswith("RATIONALE:"):
                rationale = line.split(":", 1)[1].strip()
                current_section = "rationale"

            elif lu.startswith("WEEKLY RANGE"):
                current_section = "range"

            elif lu.startswith("LOWER BOUND:"):
                lower_bound = line.split(":", 1)[1].strip()
                current_section = "range"

            elif lu.startswith("UPPER BOUND:"):
                upper_bound = line.split(":", 1)[1].strip()
                current_section = "range"

            elif lu.startswith("CONTRA-VIEW:") or lu.startswith("CONTRA VIEW:"):
                contra = line.split(":", 1)[1].strip()
                current_section = "contra"

            else:
                # Continuation lines for multi-line sections
                if current_section == "rationale":
                    rationale += " " + line
                elif current_section == "contra":
                    contra += " " + line
                elif current_section == "range":
                    # Handle indented Lower/Upper lines without the label
                    if "lower" in lu:
                        lower_bound = line.split(":", 1)[-1].strip() if ":" in line else line
                    elif "upper" in lu:
                        upper_bound = line.split(":", 1)[-1].strip() if ":" in line else line

        # Build summary for fallback display
        summary = rationale
        if lower_bound and upper_bound:
            summary += " | Range: " + lower_bound + " – " + upper_bound
        if contra:
            summary += " | Risk: " + contra

        log.info(
            "  " + ticker + " → " + sentiment +
            " | range: " + (lower_bound or "?") + " – " + (upper_bound or "?")
        )

        return {
            "sentiment":   sentiment,
            "summary":     summary,
            "rationale":   rationale,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "contra":      contra,
        }

    except Exception as e:
        log.warning("  Perplexity failed for " + ticker + ": " + str(e))
        return {}


def sentiment_html(sentiments: list) -> str:
    if not sentiments:
        return ""

    def _color(s):
        return (
            "#1a7a3a" if s == "Bullish"
            else "#c0392b" if s == "Bearish"
            else "#b8860b"
        )

    def _badge(s):
        col = _color(s)
        return (
            "<span style='background:" + col + ";color:#fff;"
            "padding:2px 8px;border-radius:4px;font-size:10px;"
            "font-weight:700;text-transform:uppercase'>" + s + "</span>"
        )

    rows = ""
    for item in sentiments:
        bd    = "border-bottom:1px solid #21293a;background:#1c2330;color:#f0f2f5"
        lower = item.get("lower_bound", "")
        upper = item.get("upper_bound", "")
        range_str = (lower + " – " + upper) if lower and upper else "--"
        contra = item.get("contra", "") or "--"
        rows += (
            "<tr>"
            "<td style='padding:10px 12px;" + bd + ";color:#4f9ef8;"
            "font-weight:700;white-space:nowrap'>" + item["ticker"] + "</td>"
            "<td style='padding:10px 12px;" + bd + ";color:#7d8fa8'>"
            + item["name"][:18] + "</td>"
            "<td style='padding:10px 12px;" + bd + ";text-align:center'>"
            + _badge(item["sentiment"]) + "</td>"
            "<td style='padding:10px 12px;" + bd + ";font-size:11px;color:#c0cad8'>"
            + item.get("rationale", item.get("summary", ""))[:200] + "</td>"
            "<td style='padding:10px 12px;" + bd + ";font-size:11px;"
            "color:#52d68a;white-space:nowrap'>" + range_str + "</td>"
            "<td style='padding:10px 12px;" + bd + ";font-size:11px;color:#f56565'>"
            + contra[:120] + "</td>"
            "</tr>"
        )

    heads = "".join(
        "<th style='padding:8px 12px;text-align:left;background:#1c2330;"
        "color:#7d8fa8;font-size:10px;text-transform:uppercase;letter-spacing:1px'>"
        + h + "</th>"
        for h in ["Ticker", "Name", "Sentiment", "Rationale", "Weekly Range", "Contra-View"]
    )

    return (
        "<h2 style='font-size:14px;color:#f0f2f5;margin:24px 0 10px'>"
        "AI Sentiment Analysis</h2>"
        "<p style='color:#7d8fa8;font-size:11px;margin:0 0 12px'>"
        "Powered by OpenRouter · Based on last 7 days</p>"
        "<table style='width:100%;border-collapse:collapse;background:#1c2330;"
        "border-radius:8px;overflow:hidden;margin-bottom:24px'>"
        "<thead><tr>" + heads + "</tr></thead>"
        "<tbody>" + rows + "</tbody></table>"
    )
