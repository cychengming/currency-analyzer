"""Data sources for DL pipeline.

- Gold price + volume: tries Stooq CSV first; falls back to existing app fetch_historical_ohlc_data.
- USD index: tries Stooq (DXY proxy) symbol list.
- GDP: World Bank API.

All functions return plain Python lists/dicts so they can be stored to Postgres.
"""

import datetime as dt
from typing import Any, List, Dict, Optional, Union

import requests
from urllib.parse import quote


def fetch_yahoo_chart(symbol: str, rng: str, interval: str) -> List[Dict[str, Any]]:
    """Fetch OHLCV from Yahoo Finance chart API.

    Args:
      symbol: e.g. 'XAUUSD=X', 'GC=F', 'DX-Y.NYB', '^DXY'
      rng: e.g. '1d', '5d', '1mo', '3mo', '1y'
      interval: e.g. '1m', '5m', '15m', '1h', '1d'

    Returns rows sorted oldest->newest with keys:
      dt_local (YYYY-MM-DD HH:MM), date_local (YYYY-MM-DD), close, open, high, low, volume
    """

    # Yahoo symbols may contain special characters (^, =, etc.) that must be URL-encoded.
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}"
    resp = requests.get(
        url,
        params={"range": rng, "interval": interval},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json() or {}
    result = ((payload.get("chart") or {}).get("result") or [])
    if not result:
        return []

    result0 = result[0] or {}
    meta = result0.get("meta") or {}
    gmtoffset = meta.get("gmtoffset")
    try:
        gmtoffset = int(gmtoffset) if gmtoffset is not None else 0
    except Exception:
        gmtoffset = 0

    ts_list = result0.get("timestamp") or []
    quote_data = (((result0.get("indicators") or {}).get("quote") or []) or [{}])[0] or {}
    closes = quote_data.get("close") or []
    opens = quote_data.get("open") or []
    highs = quote_data.get("high") or []
    lows = quote_data.get("low") or []
    vols = quote_data.get("volume") or []

    out: List[Dict[str, Any]] = []
    for i, ts in enumerate(ts_list):
        try:
            ts_i = int(ts)
        except Exception:
            continue

        def _at(arr, idx):
            try:
                return arr[idx]
            except Exception:
                return None

        close = _at(closes, i)
        if close is None:
            continue

        try:
            # Convert to exchange-local time using gmtoffset.
            local_dt = dt.datetime.utcfromtimestamp(ts_i + gmtoffset)
            dt_local = local_dt.strftime("%Y-%m-%d %H:%M")
            date_local = local_dt.strftime("%Y-%m-%d")
        except Exception:
            continue

        def _f(v) -> Optional[float]:
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        out.append(
            {
                "dt_local": dt_local,
                "date_local": date_local,
                "open": _f(_at(opens, i)),
                "high": _f(_at(highs, i)),
                "low": _f(_at(lows, i)),
                "close": _f(close),
                "volume": _f(_at(vols, i)),
            }
        )

    out.sort(key=lambda r: r.get("dt_local") or "")
    return out


def fetch_gold_intraday_yahoo(rng: str = "5d", interval: str = "5m") -> List[Dict[str, Any]]:
    """Fetch intraday gold prices.

    Tries XAUUSD spot first, then gold futures.
    """

    for sym in ("XAUUSD=X", "GC=F"):
        try:
            rows = fetch_yahoo_chart(sym, rng=rng, interval=interval)
            if rows:
                return rows
        except Exception:
            continue
    return []


def _to_date_str(d: Union[dt.date, str]) -> str:
    if isinstance(d, str):
        return d
    return d.isoformat()


def fetch_world_bank_gdp_current_usd(country: str, start_year: int, end_year: int) -> List[Dict[str, Any]]:
    """Fetch GDP (current US$) annual values from World Bank.

    Indicator: NY.GDP.MKTP.CD
    country: ISO3 code or 'WLD' for world.

    Returns: [{"country": "USA", "year": 2020, "gdp_current_usd": 2.1e13}, ...]
    """

    # World Bank uses country code in path.
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/NY.GDP.MKTP.CD"
    params = {
        "format": "json",
        "per_page": 20000,
        "date": f"{start_year}:{end_year}",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, list) or len(payload) < 2:
        return []

    rows: List[Dict[str, Any]] = []
    for item in payload[1] or []:
        year_str = item.get("date")
        value = item.get("value")
        if year_str is None or value is None:
            continue
        try:
            year = int(year_str)
            gdp = float(value)
        except (TypeError, ValueError):
            continue
        rows.append({"country": country, "year": year, "gdp_current_usd": gdp})

    # sort ascending by year
    rows.sort(key=lambda x: x["year"])
    return rows


def fetch_stooq_daily_ohlcv(symbol: str) -> List[Dict[str, Any]]:
    """Fetch daily OHLCV from Stooq CSV endpoint.

    symbol examples (Stooq can vary):
    - 'xauusd'
    - 'dx.f' (DXY futures continuous)

    Returns list with keys: dt, open, high, low, close, volume (volume may be None).
    """

    url = "https://stooq.com/q/d/l/"
    params = {"s": symbol, "i": "d"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    text = r.text.strip().splitlines()
    if not text or len(text) < 2:
        return []

    header = [h.strip().lower() for h in text[0].split(",")]
    out: List[Dict[str, Any]] = []
    for line in text[1:]:
        parts = line.split(",")
        if len(parts) != len(header):
            continue
        row = dict(zip(header, parts))
        date_str = row.get("date")
        if not date_str:
            continue

        def f(name: str) -> Optional[float]:
            v = row.get(name)
            if v in (None, "", "-"):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        out.append(
            {
                "dt": date_str,
                "open": f("open"),
                "high": f("high"),
                "low": f("low"),
                "close": f("close"),
                "volume": f("volume"),
            }
        )

    # Oldest -> newest
    out.sort(key=lambda x: x["dt"])
    return out


def fetch_gold_daily(years: int = 30) -> List[Dict[str, Any]]:
    """Fetch gold daily close+volume for ~N years.

    Tries Stooq first; then falls back to app's existing historical OHLC endpoint logic.
    """

    # Prefer Stooq XAUUSD for spot; then try a few alternates.
    # (Yahoo's chart endpoint currently returns 404 for XAUUSD=X in this environment.)
    stooq_candidates = ["xauusd", "gold", "gc.f"]
    for sym in stooq_candidates:
        try:
            rows = fetch_stooq_daily_ohlcv(sym)
            if rows:
                # keep only last N years
                cutoff = (dt.date.today() - dt.timedelta(days=int(years * 365.25))).isoformat()
                rows = [r for r in rows if r.get("dt") and r["dt"] >= cutoff]
                return [{"dt": r["dt"], "close": float(r["close"]), "volume": r.get("volume")} for r in rows if r.get("close") is not None]
        except Exception:
            continue

    # Fallback: use existing currency module to fetch GOLD/USD
    from modules.currency import fetch_historical_ohlc_data

    days = int(years * 365.25)
    data = fetch_historical_ohlc_data("GOLD/USD", days)
    rows = []
    for p in data or []:
        dts = p.get("date")
        close = p.get("close")
        if dts is None or close is None:
            continue
        try:
            rows.append({"dt": str(dts), "close": float(close), "volume": p.get("volume")})
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda x: x["dt"])
    return rows


def fetch_gold_daily_ohlc(years: int = 30) -> List[Dict[str, Any]]:
    """Fetch gold daily OHLCV for ~N years.

    This is used for intraday *range* (High→Low) statistics over long windows.
    Daily OHLC contains the day's high and low, which is the intraday range.

    Returns rows with: dt, open, high, low, close, volume.
    """

    cutoff = (dt.date.today() - dt.timedelta(days=int(years * 365.25))).isoformat()

    # Prefer Stooq XAUUSD for spot daily OHLC.
    stooq_candidates = ["xauusd", "gold", "gc.f"]
    for sym in stooq_candidates:
        try:
            rows = fetch_stooq_daily_ohlcv(sym)
            if rows:
                rows = [r for r in rows if r.get("dt") and r["dt"] >= cutoff]
                out = []
                for r in rows:
                    if r.get("high") is None or r.get("low") is None or r.get("close") is None:
                        continue
                    out.append(
                        {
                            "dt": r["dt"],
                            "open": r.get("open"),
                            "high": float(r["high"]),
                            "low": float(r["low"]),
                            "close": float(r["close"]),
                            "volume": r.get("volume"),
                        }
                    )
                if out:
                    out.sort(key=lambda x: x["dt"])
                    return out
        except Exception:
            continue

    # Fallback: Yahoo chart (futures). Yahoo returns 404 for XAUUSD=X here.
    rng = "max" if years >= 10 else ("5y" if years >= 5 else ("2y" if years >= 2 else ("1y" if years >= 1 else "6mo")))
    for sym in ("GC=F",):
        try:
            y = fetch_yahoo_chart(sym, rng=rng, interval="1d")
            if y:
                out = []
                for r in y:
                    dts = r.get("date_local")
                    if not dts or str(dts) < cutoff:
                        continue
                    hi = r.get("high")
                    lo = r.get("low")
                    cl = r.get("close")
                    if hi is None or lo is None or cl is None:
                        continue
                    out.append(
                        {
                            "dt": str(dts),
                            "open": r.get("open"),
                            "high": float(hi),
                            "low": float(lo),
                            "close": float(cl),
                            "volume": r.get("volume"),
                        }
                    )
                if out:
                    out.sort(key=lambda x: x["dt"])
                    return out
        except Exception:
            continue

    # Fallback: use existing currency module to fetch GOLD/USD daily OHLC.
    from modules.currency import fetch_historical_ohlc_data

    days = int(years * 365.25)
    data = fetch_historical_ohlc_data("GOLD/USD", days)
    out = []
    for p in data or []:
        dts = p.get("date")
        if not dts:
            continue
        if str(dts) < cutoff:
            continue
        try:
            high = p.get("high")
            low = p.get("low")
            close = p.get("close")
            if high is None or low is None or close is None:
                continue
            out.append(
                {
                    "dt": str(dts),
                    "open": p.get("open"),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": p.get("volume"),
                }
            )
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda x: x["dt"])
    return out


def fetch_usd_index_daily(years: int = 30) -> List[Dict[str, Any]]:
    """Fetch an approximation of USD dollar index (DXY) daily close.

    This is a best-effort fetch:
    - Try Stooq daily history first
    - Fall back to Yahoo Finance chart API (often available even when other Yahoo endpoints are blocked)
    """

    candidates = ["dx.f", "dxy", "dxy.us"]
    for sym in candidates:
        try:
            rows = fetch_stooq_daily_ohlcv(sym)
            if rows:
                cutoff = (dt.date.today() - dt.timedelta(days=int(years * 365.25))).isoformat()
                rows = [r for r in rows if r.get("dt") and r["dt"] >= cutoff]
                return [{"dt": r["dt"], "close": float(r["close"])} for r in rows if r.get("close") is not None]
        except Exception:
            continue

    # Yahoo Finance chart API fallback
    # Common DXY symbols: 'DX-Y.NYB' (ICE US Dollar Index) and '^DXY'
    def _fetch_yahoo_daily_close(symbol: str) -> List[Dict[str, Any]]:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

        # Use supported ranges similar to modules.currency
        if years >= 10:
            rng = "10y"
        elif years >= 5:
            rng = "5y"
        elif years >= 2:
            rng = "2y"
        elif years >= 1:
            rng = "1y"
        else:
            rng = "6mo"

        resp = requests.get(
            url,
            params={"range": rng, "interval": "1d"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json() or {}
        chart = (payload.get("chart") or {}).get("result")
        if not chart:
            return []

        result = chart[0] or {}
        ts_list = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0] or {}
        closes = quote.get("close") or []

        out: List[Dict[str, Any]] = []
        cutoff = (dt.date.today() - dt.timedelta(days=int(years * 365.25))).isoformat()
        for ts, close in zip(ts_list, closes):
            if close is None:
                continue
            try:
                date_str = dt.datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
            except Exception:
                continue
            if date_str < cutoff:
                continue
            try:
                out.append({"dt": date_str, "close": float(close)})
            except (TypeError, ValueError):
                continue

        out.sort(key=lambda x: x["dt"])
        return out

    for sym in ["DX-Y.NYB", "^DXY"]:
        try:
            rows = _fetch_yahoo_daily_close(sym)
            if rows:
                return rows
        except Exception:
            continue

    return []
