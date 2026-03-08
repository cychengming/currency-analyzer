"""Deep-learning pipeline: ingest macro data to Postgres and train an RNN model.

This is intentionally separate from the main Flask/SQLite application.

Commands:
  python -m modules.dl_pipeline ingest
  python -m modules.dl_pipeline train --model gru --horizon-days 365
  python -m modules.dl_pipeline forecast --run-id <id>

Env:
  POSTGRES_DSN=postgresql+psycopg2://currency:currency@localhost:5432/currency_analyzer

Install dependencies:
  pip install -r requirements-dl.txt
"""

import argparse
import datetime as dt
import math
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from modules.dl_postgres import DLIngestConfig, get_engine, init_dl_schema
from modules.dl_schema import GoldDaily, GdpAnnual, UsdIndexDaily, ForecastRun, GoldForecastDaily
from modules.dl_sources import (
    fetch_gold_daily,
    fetch_gold_daily_ohlc,
    fetch_usd_index_daily,
    fetch_world_bank_gdp_current_usd,
    fetch_gold_intraday_yahoo,
)


def _rolling_std(values: List[float], window: int) -> List[float]:
    """Population rolling standard deviation with O(n) time.

    Returns a list aligned to input where entries before a full window are NaN.
    """

    if window <= 1:
        return [float("nan")] * len(values)

    out = [float("nan")] * len(values)
    sum_x = 0.0
    sum_x2 = 0.0

    for i, x in enumerate(values):
        sum_x += x
        sum_x2 += x * x

        if i >= window:
            x_old = values[i - window]
            sum_x -= x_old
            sum_x2 -= x_old * x_old

        if i >= window - 1:
            mean = sum_x / window
            var = (sum_x2 / window) - (mean * mean)
            if var < 0.0:
                var = 0.0
            out[i] = math.sqrt(var)

    return out


def export_gold_daily_sigma(window_days: int = 30, annualize: bool = False, limit: int = 0) -> None:
    """Print rolling daily sigma for gold to stdout as CSV.

    Sigma is computed on daily log-returns: r_t = ln(P_t / P_{t-1}).
    The reported sigma at date t uses the trailing `window_days` returns ending at t.
    """

    engine = get_engine()
    init_dl_schema(engine)

    with Session(engine) as session:
        gold = session.query(GoldDaily).order_by(GoldDaily.dt.asc()).all()

    if len(gold) < 3:
        raise SystemExit("Not enough gold data in Postgres. Run ingest first.")

    dates = [r.dt for r in gold]
    closes = [float(r.close) for r in gold]

    # Compute log returns aligned to dates: returns[0] = 0 by convention
    eps = 1e-12
    returns = [0.0] * len(closes)
    for i in range(1, len(closes)):
        a = float(closes[i - 1]) + eps
        b = float(closes[i]) + eps
        returns[i] = math.log(b / a)

    sigma = _rolling_std(returns[1:], window=int(window_days))
    # Align back to dates (sigma for date i uses returns up to i)
    sigma = [float("nan")] + sigma

    scale = math.sqrt(252.0) if annualize else 1.0

    rows = []
    for d, s in zip(dates, sigma):
        if not math.isfinite(s):
            continue
        rows.append((d, s * scale))

    if limit and limit > 0:
        rows = rows[-int(limit) :]

    print("dt,sigma" + ("_ann" if annualize else ""))
    for d, s in rows:
        print(f"{d},{s:.8f}")


def intraday_sigma(
    window_bars: int = 300,
    rng: str = "5d",
    interval: str = "5m",
) -> None:
    """Compute intraday sigma and sigma-multiples from Yahoo intraday bars.

    Definitions:
      - bar log return: r_i = ln(P_i / P_{i-1})
      - sigma_bar: std(r) over the last `window_bars` bars
      - z_last_bar: last bar return / sigma_bar
      - session_move_z: ln(P_last / P_open_today) / (sigma_bar * sqrt(n_bars_today))

    Notes:
      - Yahoo intraday ranges are limited (e.g., 1m bars only for a few days).
      - Times are exchange-local (per Yahoo gmtoffset).
    """

    rows = fetch_gold_intraday_yahoo(rng=rng, interval=interval)
    if not rows or len(rows) < max(10, window_bars + 2):
        raise SystemExit(f"Not enough intraday rows (got {len(rows)}). Try a larger range or smaller window.")

    # Extract closes and local dates
    closes: List[float] = []
    dates_local: List[str] = []
    dt_local: List[str] = []
    for r in rows:
        c = r.get("close")
        d = r.get("date_local")
        t = r.get("dt_local")
        if c is None or d is None or t is None:
            continue
        try:
            closes.append(float(c))
            dates_local.append(str(d))
            dt_local.append(str(t))
        except Exception:
            continue

    if len(closes) < max(10, window_bars + 2):
        raise SystemExit(f"Not enough usable intraday closes (got {len(closes)}).")

    # Bar returns
    eps = 1e-12
    rets: List[float] = [0.0] * len(closes)
    for i in range(1, len(closes)):
        rets[i] = math.log((closes[i] + eps) / (closes[i - 1] + eps))

    # Sigma over last window_bars returns
    w = int(window_bars)
    if w < 2:
        raise SystemExit("window_bars must be >= 2")
    tail = rets[-w:]
    mu = sum(tail) / w
    var = sum((x - mu) * (x - mu) for x in tail) / w
    if var < 0.0:
        var = 0.0
    sigma_bar = math.sqrt(var)

    last_ret = rets[-1]
    z_last_bar = (last_ret / sigma_bar) if sigma_bar > 0 else float("nan")

    # Session move: from first bar of latest local day to last bar
    last_day = dates_local[-1]
    start_idx = None
    for i in range(len(dates_local) - 1, -1, -1):
        if dates_local[i] != last_day:
            start_idx = i + 1
            break
    if start_idx is None:
        start_idx = 0

    p_open = closes[start_idx]
    p_last = closes[-1]
    n_bars_today = max(1, len(closes) - start_idx - 1)
    session_log_move = math.log((p_last + eps) / (p_open + eps))
    session_move_z = (
        session_log_move / (sigma_bar * math.sqrt(float(n_bars_today)))
        if sigma_bar > 0
        else float("nan")
    )

    print(
        {
            "interval": interval,
            "range": rng,
            "window_bars": w,
            "sigma_bar": sigma_bar,
            "last_bar": {
                "dt_local": dt_local[-1],
                "log_return": last_ret,
                "approx_pct": (math.exp(last_ret) - 1.0) * 100.0,
                "z": z_last_bar,
            },
            "session": {
                "date_local": last_day,
                "start_dt_local": dt_local[start_idx],
                "end_dt_local": dt_local[-1],
                "bars": int(n_bars_today),
                "log_move": session_log_move,
                "approx_pct": (math.exp(session_log_move) - 1.0) * 100.0,
                "z": session_move_z,
            },
        }
    )


def _load_gold_ohlc_from_db(years: int = 10) -> List[Dict[str, Any]]:
    """Load daily gold OHLC from Postgres (if available).

    Returns rows with keys: dt, open, high, low, close, volume.
    Some older ingests may have null open/high/low; callers should handle.
    """

    engine = get_engine()
    init_dl_schema(engine)

    cutoff = (dt.date.today() - dt.timedelta(days=int(years * 365.25))).isoformat()
    with Session(engine) as session:
        gold = (
            session.query(GoldDaily)
            .filter(GoldDaily.dt >= cutoff)
            .order_by(GoldDaily.dt.asc())
            .all()
        )

    out: List[Dict[str, Any]] = []
    for r in gold:
        out.append(
            {
                "dt": r.dt,
                "open": getattr(r, "open", None),
                "high": getattr(r, "high", None),
                "low": getattr(r, "low", None),
                "close": float(r.close),
                "volume": (float(r.volume) if r.volume is not None else None),
            }
        )
    return out


def gold_range_sigma(
    years: int = 10,
    window_days: int = 252,
    use_log: bool = True,
    limit: int = 10,
) -> None:
    """Compute High→Low range z-scores using daily OHLC.

    This matches the common finance narrative of "intraday move" using the day's
    High and Low from daily bars (not 5-minute data).

    Range definition:
      - log range (default): x_t = ln(high/low)
      - pct range: x_t = (high-low)/high

    Z-score:
      z_t = (x_t - mu_t) / sigma_t
    where mu_t and sigma_t are rolling over `window_days`.
    """

    rows = _load_gold_ohlc_from_db(years=int(years))
    # Ensure we actually have high/low data stored; otherwise fall back to fetching.
    if not rows or sum(1 for r in rows if r.get("high") is not None and r.get("low") is not None) < int(window_days) + 10:
        rows = fetch_gold_daily_ohlc(years=int(years))
    if not rows or len(rows) < int(window_days) + 10:
        raise SystemExit(f"Not enough daily OHLC rows (got {len(rows)}). Try more years or smaller window.")

    xs: List[float] = []
    dts: List[str] = []
    eps = 1e-12
    for r in rows:
        hi = r.get("high")
        lo = r.get("low")
        dt_s = r.get("dt")
        if hi is None or lo is None or not dt_s:
            continue
        try:
            hi = float(hi)
            lo = float(lo)
        except Exception:
            continue
        if hi <= 0 or lo <= 0:
            continue

        if use_log:
            x = math.log((hi + eps) / (lo + eps))
        else:
            x = (hi - lo) / (hi + eps)

        xs.append(float(x))
        dts.append(str(dt_s))

    if len(xs) < int(window_days) + 10:
        raise SystemExit("Not enough usable OHLC rows after filtering.")

    w = int(window_days)
    out_rows = []
    s = 0.0
    s2 = 0.0
    for i, x in enumerate(xs):
        s += x
        s2 += x * x
        if i >= w:
            xo = xs[i - w]
            s -= xo
            s2 -= xo * xo

        if i >= w - 1:
            mu = s / w
            var = (s2 / w) - (mu * mu)
            if var < 0.0:
                var = 0.0
            sig = math.sqrt(var)
            z = (x - mu) / sig if sig > 0 else float("nan")
            out_rows.append({"dt": dts[i], "x": x, "mu": mu, "sigma": sig, "z": z})

    if limit and limit > 0:
        out_rows = out_rows[-int(limit) :]

    print(
        {
            "years": int(years),
            "window_days": w,
            "range_def": "log(high/low)" if use_log else "(high-low)/high",
            "rows": out_rows,
        }
    )


def gold_hilo_drop_over_daily_sigma(
    years: int = 10,
    window_days: int = 252,
    limit: int = 10,
) -> None:
    """Replicate the requested '4.75σ' definition.

    Numerator x:
      High→Low percent drop (positive): x_t = (H_t - L_t) / H_t

        Denominator σ:
            Different sources use different daily-return definitions; we compute both:
                - simple returns: r_t = (C_t - C_{t-1}) / C_{t-1}
                - log returns:    lr_t = ln(C_t / C_{t-1})

        Z-style ratio:
            z_t = x_t / σ_t

    We use σ_t computed from returns up to the *previous* day to avoid mixing the same day's move
    into its own denominator.
    """

    rows = _load_gold_ohlc_from_db(years=int(years))
    if not rows or sum(1 for r in rows if r.get("high") is not None and r.get("low") is not None) < int(window_days) + 10:
        rows = fetch_gold_daily_ohlc(years=int(years))
    if not rows or len(rows) < int(window_days) + 10:
        raise SystemExit(f"Not enough daily OHLC rows (got {len(rows)}). Try more years or smaller window.")

    dts: List[str] = []
    highs: List[float] = []
    lows: List[float] = []
    closes: List[float] = []
    for r in rows:
        dt_s = r.get("dt")
        hi = r.get("high")
        lo = r.get("low")
        cl = r.get("close")
        if not dt_s or hi is None or lo is None or cl is None:
            continue
        try:
            hi_f = float(hi)
            lo_f = float(lo)
            cl_f = float(cl)
        except Exception:
            continue
        if hi_f <= 0 or lo_f <= 0 or cl_f <= 0:
            continue
        dts.append(str(dt_s))
        highs.append(hi_f)
        lows.append(lo_f)
        closes.append(cl_f)

    if len(closes) < int(window_days) + 10:
        raise SystemExit("Not enough usable OHLC rows after filtering.")

    # Close-to-close simple returns and log returns (aligned): [0]=0 by convention
    returns = [0.0] * len(closes)
    log_returns = [0.0] * len(closes)
    eps = 1e-12
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        returns[i] = (closes[i] - prev) / prev if prev != 0 else 0.0
        log_returns[i] = math.log((closes[i] + eps) / (prev + eps))

    # Rolling sigma of returns (population std) over window_days, aligned to date index.
    # sigma_ret[i] uses returns[i-window_days+1..i]
    sigma_ret = _rolling_std(returns[1:], window=int(window_days))
    sigma_ret = [float("nan")] + sigma_ret

    sigma_log_ret = _rolling_std(log_returns[1:], window=int(window_days))
    sigma_log_ret = [float("nan")] + sigma_log_ret

    out_rows = []
    w = int(window_days)
    for i in range(len(dts)):
        if i < w:
            continue
        # Use sigma from previous day to avoid leakage
        sig = sigma_ret[i - 1]
        sig_log = sigma_log_ret[i - 1]
        if (not math.isfinite(sig) or sig <= 0) and (not math.isfinite(sig_log) or sig_log <= 0):
            continue

        x = (highs[i] - lows[i]) / highs[i]
        z = x / sig if (math.isfinite(sig) and sig > 0) else float("nan")
        z_log = x / sig_log if (math.isfinite(sig_log) and sig_log > 0) else float("nan")

        out_rows.append(
            {
                "dt": dts[i],
                "hilo_drop_pct": x * 100.0,
                "sigma_simple_daily_return_pct": (sig * 100.0) if math.isfinite(sig) else None,
                "z_simple": z,
                "sigma_log_daily_return_pct": (sig_log * 100.0) if math.isfinite(sig_log) else None,
                "z_log": z_log,
            }
        )

    if limit and limit > 0:
        out_rows = out_rows[-int(limit) :]

    print(
        {
            "years": int(years),
            "window_days": int(window_days),
            "numerator": "(high-low)/high",
            "denominator": "std(close_to_close_return) (simple + log)",
            "rows": out_rows,
        }
    )


def gold_atr(
    years: int = 10,
    window_days: int = 14,
    method: str = "wilder",
    limit: int = 10,
) -> None:
    """Compute Average True Range (ATR) for gold using daily OHLC.

    True Range (TR) for day t:
      TR_t = max(
        High_t - Low_t,
        abs(High_t - Close_{t-1}),
        abs(Low_t - Close_{t-1})
      )

    ATR (Wilder's smoothing, standard in trading platforms):
      ATR_t = (ATR_{t-1} * (N-1) + TR_t) / N

    Alternative: simple moving average of TR over N days.
    """

    rows = _load_gold_ohlc_from_db(years=int(years))
    usable = [r for r in rows if r.get("high") is not None and r.get("low") is not None and r.get("close") is not None]
    if len(usable) < int(window_days) + 2:
        raise SystemExit(f"Not enough OHLC rows in Postgres (got {len(usable)}). Run ingest first.")

    dts: List[str] = []
    highs: List[float] = []
    lows: List[float] = []
    closes: List[float] = []
    for r in usable:
        try:
            dts.append(str(r["dt"]))
            highs.append(float(r["high"]))
            lows.append(float(r["low"]))
            closes.append(float(r["close"]))
        except Exception:
            continue

    n = int(window_days)
    if n < 2:
        raise SystemExit("window_days must be >= 2")

    # Compute TR series (aligned). TR[0]=NaN because needs prev close.
    tr: List[float] = [float("nan")] * len(closes)
    for i in range(1, len(closes)):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)

    # ATR series
    atr: List[float] = [float("nan")] * len(closes)
    method_l = (method or "wilder").strip().lower()

    # Seed ATR with SMA of first N TR values (common practice)
    seed_start = 1
    seed_end = 1 + n
    if seed_end >= len(tr):
        raise SystemExit("Not enough data to seed ATR")
    seed_vals = [x for x in tr[seed_start:seed_end] if math.isfinite(x)]
    if len(seed_vals) != n:
        raise SystemExit("Missing TR values while seeding ATR")
    atr_seed = sum(seed_vals) / n
    atr[seed_end - 1] = atr_seed

    if method_l in ("sma", "simple"):
        # Rolling SMA of TR
        # Compute SMA(TR) for each i >= seed_end-1
        s = sum(seed_vals)
        for i in range(seed_end, len(tr)):
            x_new = tr[i]
            x_old = tr[i - n]
            if not math.isfinite(x_new) or not math.isfinite(x_old):
                atr[i] = float("nan")
            else:
                s += x_new - x_old
                atr[i] = s / n
    else:
        # Wilder smoothing
        prev_atr = atr_seed
        for i in range(seed_end, len(tr)):
            x = tr[i]
            if not math.isfinite(x):
                atr[i] = float("nan")
                continue
            prev_atr = (prev_atr * (n - 1) + x) / n
            atr[i] = prev_atr

    out_rows = []
    for i in range(len(dts)):
        if not math.isfinite(atr[i]):
            continue
        atr_pct = (atr[i] / closes[i]) * 100.0 if closes[i] != 0 else float("nan")
        out_rows.append(
            {
                "dt": dts[i],
                "close": closes[i],
                "tr": tr[i],
                "atr": atr[i],
                "atr_pct": atr_pct,
            }
        )

    if limit and limit > 0:
        out_rows = out_rows[-int(limit) :]

    print(
        {
            "window_days": n,
            "method": "wilder" if method_l not in ("sma", "simple") else "sma",
            "rows": out_rows,
        }
    )


def _upsert_by_unique(session: Session, model_cls, unique_filter: Dict[str, Any], values: Dict[str, Any]) -> None:
    obj = session.query(model_cls).filter_by(**unique_filter).one_or_none()
    if obj is None:
        obj = model_cls(**values)
        session.add(obj)
    else:
        for k, v in values.items():
            setattr(obj, k, v)


def ingest(years: int = 30, gdp_countries: Tuple[str, ...] = ("WLD", "USA", "CHN", "EUU", "JPN", "IND")) -> None:
    engine = get_engine()
    init_dl_schema(engine)

    # Prefer OHLC so Postgres stores high/low and we can compute High→Low metrics from DB.
    gold_ohlc = fetch_gold_daily_ohlc(years=years)
    gold = gold_ohlc if gold_ohlc else fetch_gold_daily(years=years)
    usd = fetch_usd_index_daily(years=years)

    end_year = dt.date.today().year
    start_year = end_year - years
    gdp_rows: List[Dict[str, Any]] = []
    for c in gdp_countries:
        try:
            gdp_rows.extend(fetch_world_bank_gdp_current_usd(c, start_year, end_year))
        except Exception:
            # Keep ingest robust; partial GDP is okay
            continue

    with Session(engine) as session:
        for r in gold:
            v_open = r.get("open")
            v_high = r.get("high")
            v_low = r.get("low")
            _upsert_by_unique(
                session,
                GoldDaily,
                {"dt": r["dt"]},
                {
                    "dt": r["dt"],
                    "open": (float(v_open) if v_open is not None else None),
                    "high": (float(v_high) if v_high is not None else None),
                    "low": (float(v_low) if v_low is not None else None),
                    "close": float(r["close"]),
                    "volume": (float(r["volume"]) if r.get("volume") is not None else None),
                },
            )

        for r in usd:
            _upsert_by_unique(session, UsdIndexDaily, {"dt": r["dt"]}, {"dt": r["dt"], "close": float(r["close"])})

        for r in gdp_rows:
            _upsert_by_unique(
                session,
                GdpAnnual,
                {"country": r["country"], "year": int(r["year"])},
                {"country": r["country"], "year": int(r["year"]), "gdp_current_usd": float(r["gdp_current_usd"])},
            )

        session.commit()

    print(f"[OK] Ingested: gold={len(gold)} usd_index={len(usd)} gdp={len(gdp_rows)}")


def _require_torch():
    try:
        import torch  # noqa: F401

        return
    except Exception as e:
        raise SystemExit(
            "PyTorch is required for training. Install with: pip install -r requirements-dl.txt\n"
            f"Import error: {e}"
        )


def _is_gold_asset(asset: str) -> bool:
    a = (asset or "").strip().upper()
    return a in ("GOLD", "GOLD/USD", "XAUUSD", "XAUUSD/USD")


def train(model: str = "gru", lookback_days: int = 120, horizon_days: int = 365, asset: str = "GOLD/USD", years: int = 30) -> int:
    """Train a small GRU/LSTM model and store a 1-year forecast into Postgres.

    Forecast strategy: recursive next-day prediction for horizon_days.
    """

    _require_torch()
    import numpy as np
    import torch
    from torch import nn

    engine = get_engine()
    init_dl_schema(engine)

    asset = str(asset or "GOLD/USD").strip() or "GOLD/USD"
    years = int(years) if years is not None else 30
    years = max(1, min(int(years), 60))

    with Session(engine) as session:
        gold = session.query(GoldDaily).order_by(GoldDaily.dt.asc()).all()
        usd = session.query(UsdIndexDaily).order_by(UsdIndexDaily.dt.asc()).all()
        gdp = session.query(GdpAnnual).order_by(GdpAnnual.year.asc()).all()

    if not gold and _is_gold_asset(asset):
        raise SystemExit("Not enough gold data in Postgres. Run ingest first.")

    # Build aligned daily series by date.
    # For gold, we use Postgres gold_daily. For other assets, we fetch via the main app data fetcher.
    # Macro series are best-effort (forward-filled or 0).
    usd_map = {r.dt: r.close for r in usd}

    dates = []
    closes = None
    volumes = None

    if _is_gold_asset(asset):
        gold_map = {r.dt: (r.close, r.volume) for r in gold}
        dates = sorted(gold_map.keys())
        if len(dates) < lookback_days + 10:
            raise SystemExit("Not enough daily gold data to train. Run ingest first.")
        closes = np.array([gold_map[d][0] for d in dates], dtype=np.float32)
        volumes = np.array([(gold_map[d][1] or 0.0) for d in dates], dtype=np.float32)
    else:
        from modules.currency import fetch_historical_ohlc_data

        days = int(years * 365.25)
        rows = fetch_historical_ohlc_data(asset, days)
        if not rows:
            raise SystemExit(f"No OHLC data found for asset={asset}")

        dates = [str(r.get("date")) for r in rows if r.get("date") and r.get("close") is not None]
        closes_list = []
        vols_list = []
        for r in rows:
            d = r.get("date")
            c = r.get("close")
            if not d or c is None:
                continue
            try:
                closes_list.append(float(c))
            except (TypeError, ValueError):
                continue
            v = r.get("volume")
            try:
                vols_list.append(float(v) if v is not None else 0.0)
            except (TypeError, ValueError):
                vols_list.append(0.0)

        if len(closes_list) < lookback_days + 10:
            raise SystemExit(f"Not enough data to train for asset={asset}. Need more history.")

        closes = np.array(closes_list, dtype=np.float32)
        volumes = np.array(vols_list, dtype=np.float32)

    if closes is None or volumes is None or not dates:
        raise SystemExit("Failed to build training series")
    # USD index: forward-fill missing values, then compute both level and return features.
    usd_close = np.zeros_like(closes)
    last_usd = None
    for i, d in enumerate(dates):
        v = usd_map.get(d)
        if v is None:
            if last_usd is not None:
                usd_close[i] = float(last_usd)
            else:
                usd_close[i] = 0.0
        else:
            try:
                last_usd = float(v)
            except (TypeError, ValueError):
                last_usd = last_usd
            usd_close[i] = float(last_usd) if last_usd is not None else 0.0

    # GDP annual: map each day to the latest available GDP value for that year (default: WLD).
    # GDP changes yearly, so this becomes a slowly-varying macro feature.
    # If WLD is missing, fall back to the first available country series.
    gdp_feature = np.zeros_like(closes)
    if gdp:
        preferred = [r for r in gdp if (r.country or '').upper() == 'WLD']
        if preferred:
            series = preferred
        else:
            first_country = (gdp[0].country or '').upper()
            series = [r for r in gdp if (r.country or '').upper() == first_country]
        by_year = {}
        for r in series:
            try:
                yr = int(r.year)
                val = float(r.gdp_current_usd)
            except (TypeError, ValueError):
                continue
            # Keep the latest value for the year (should be unique anyway)
            by_year[yr] = val

        if by_year:
            years_sorted = sorted(by_year.keys())

            def gdp_for_year(yr: int) -> float:
                if yr in by_year:
                    return float(by_year[yr])
                # Backfill with most recent earlier year
                earlier = [y for y in years_sorted if y <= yr]
                if earlier:
                    return float(by_year[earlier[-1]])
                return 0.0

            for i, d in enumerate(dates):
                try:
                    yr = int(str(d)[:4])
                except Exception:
                    yr = None
                gdp_feature[i] = gdp_for_year(yr) if yr is not None else 0.0

    # Features
    # - gold_return: next-day target is based on this
    # - volume_z
    # - usd_level_z (DXY level, forward-filled)
    # - usd_return_z (DXY daily return)
    # - gdp_level_z (annual GDP level mapped to each day)
    eps = 1e-6
    returns = np.zeros_like(closes)
    returns[1:] = np.log((closes[1:] + eps) / (closes[:-1] + eps))

    # Cap for predicted daily log-returns to keep recursive forecasts stable.
    # Use a multiple of historical volatility, with sensible absolute bounds.
    hist_sd = float(np.std(returns[1:]) + 1e-6)
    ret_cap = float(np.clip(5.0 * hist_sd, 0.01, 0.10))

    usd_returns = np.zeros_like(usd_close)
    # If usd_close is all zeros (no DXY data), this stays zeros.
    usd_returns[1:] = np.log((usd_close[1:] + eps) / (usd_close[:-1] + eps))

    def z(x):
        mu = float(x.mean())
        sd = float(x.std() + 1e-6)
        return (x - mu) / sd, mu, sd

    vol_z, _, _ = z(volumes)
    usd_z, _, _ = z(usd_close)
    usd_ret_z, _, _ = z(usd_returns)
    gdp_z, _, _ = z(gdp_feature)

    X = np.stack([returns, vol_z, usd_z, usd_ret_z, gdp_z], axis=1)  # [T, F]

    # Supervised windows: predict next-day return
    xs = []
    ys = []
    for i in range(lookback_days, len(X) - 1):
        xs.append(X[i - lookback_days : i])
        ys.append(returns[i + 1])

    X_t = torch.tensor(np.array(xs), dtype=torch.float32)  # [N, L, F]
    y_t = torch.tensor(np.array(ys), dtype=torch.float32).unsqueeze(-1)  # [N, 1]

    class RNN(nn.Module):
        def __init__(self, cell: str, input_size: int, hidden: int = 32):
            super().__init__()
            if cell == "lstm":
                self.rnn = nn.LSTM(input_size, hidden, batch_first=True)
            else:
                self.rnn = nn.GRU(input_size, hidden, batch_first=True)
            self.head = nn.Sequential(nn.Linear(hidden, 16), nn.ReLU(), nn.Linear(16, 1))
            self.ret_cap = float(ret_cap)

        def forward(self, x):
            out, _ = self.rnn(x)
            last = out[:, -1, :]
            raw = self.head(last)
            # Bound predicted return to [-ret_cap, ret_cap]
            return self.ret_cap * torch.tanh(raw)

    cell = "lstm" if model.lower() == "lstm" else "gru"
    net = RNN(cell, input_size=X.shape[1])

    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    net.train()
    for epoch in range(15):
        opt.zero_grad()
        pred = net(X_t)
        loss = loss_fn(pred, y_t)
        loss.backward()
        opt.step()

        if epoch in (0, 4, 9, 14):
            print(f"epoch={epoch+1} loss={float(loss):.6f}")

    # Forecast recursively for horizon_days
    net.eval()
    last_close = float(closes[-1])
    window = X[-lookback_days:].copy()  # [L, F]

    forecast = []
    current_date = dt.date.fromisoformat(dates[-1])

    with torch.no_grad():
        for _ in range(horizon_days):
            x_in = torch.tensor(window[None, :, :], dtype=torch.float32)
            next_ret = float(net(x_in).cpu().numpy().reshape(-1)[0])
            if not np.isfinite(next_ret):
                next_ret = 0.0
            next_ret = float(np.clip(next_ret, -ret_cap, ret_cap))
            next_close = last_close * float(np.exp(next_ret))

            current_date = current_date + dt.timedelta(days=1)
            forecast.append({"dt": current_date.isoformat(), "predicted_close": next_close})

            # Build next feature row:
            # - return is predicted
            # - keep volume/usd/gdp macro features frozen at last known values
            next_row = np.array([next_ret, window[-1, 1], window[-1, 2], window[-1, 3], window[-1, 4]], dtype=np.float32)
            window = np.vstack([window[1:], next_row])
            last_close = next_close

    run_id: int
    with Session(engine) as session:
        run = ForecastRun(
            created_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            model_type=cell,
            lookback_days=int(lookback_days),
            horizon_days=int(horizon_days),
            asset=str(asset),
            notes="recursive next-day return forecast",
        )
        session.add(run)
        session.flush()
        run_id = int(run.id)

        if _is_gold_asset(asset):
            for row in forecast:
                session.add(GoldForecastDaily(run_id=run_id, dt=row["dt"], predicted_close=float(row["predicted_close"])))
        else:
            from modules.dl_schema import AssetForecastDaily

            for row in forecast:
                session.add(AssetForecastDaily(run_id=run_id, dt=row["dt"], predicted_close=float(row["predicted_close"])))

        session.commit()

    print(f"[OK] Saved forecast run_id={run_id} rows={len(forecast)}")
    return run_id


def export_forecast(run_id: int) -> None:
    engine = get_engine()
    init_dl_schema(engine)

    with Session(engine) as session:
        run = session.query(ForecastRun).filter(ForecastRun.id == int(run_id)).one_or_none()
        if run is None:
            raise SystemExit(f"Run not found: {run_id}")
        rows = (
            session.query(GoldForecastDaily)
            .filter(GoldForecastDaily.run_id == int(run_id))
            .order_by(GoldForecastDaily.dt.asc())
            .all()
        )

    # Print JSON-ish lines to stdout (simple and greppable)
    print(
        {
            "run": {
                "id": int(run.id),
                "created_at": run.created_at,
                "model_type": run.model_type,
                "lookback_days": int(run.lookback_days),
                "horizon_days": int(run.horizon_days),
                "notes": run.notes,
            },
            "forecast": [{"dt": r.dt, "predicted_close": float(r.predicted_close)} for r in rows],
        }
    )


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("--years", type=int, default=30)

    p_train = sub.add_parser("train")
    p_train.add_argument("--model", choices=["gru", "lstm"], default="gru")
    p_train.add_argument("--lookback-days", type=int, default=120)
    p_train.add_argument("--horizon-days", type=int, default=365)
    p_train.add_argument("--asset", type=str, default="GOLD/USD")
    p_train.add_argument("--years", type=int, default=30)

    p_export = sub.add_parser("forecast")
    p_export.add_argument("--run-id", type=int, required=True)

    p_vol = sub.add_parser("volatility")
    p_vol.add_argument("--window-days", type=int, default=30)
    p_vol.add_argument("--annualize", action="store_true")
    p_vol.add_argument("--limit", type=int, default=0)

    p_intra = sub.add_parser("intraday-sigma")
    p_intra.add_argument("--interval", type=str, default="5m")
    p_intra.add_argument("--range", dest="rng", type=str, default="5d")
    p_intra.add_argument("--window-bars", type=int, default=300)

    p_rng = sub.add_parser("range-sigma")
    p_rng.add_argument("--years", type=int, default=10)
    p_rng.add_argument("--window-days", type=int, default=252)
    p_rng.add_argument("--pct", action="store_true", help="Use pct range (high-low)/high instead of log(high/low)")
    p_rng.add_argument("--limit", type=int, default=10)

    p_hilo = sub.add_parser("hilo-z")
    p_hilo.add_argument("--years", type=int, default=10)
    p_hilo.add_argument("--window-days", type=int, default=252)
    p_hilo.add_argument("--limit", type=int, default=10)

    p_atr = sub.add_parser("atr")
    p_atr.add_argument("--years", type=int, default=10)
    p_atr.add_argument("--window-days", type=int, default=14)
    p_atr.add_argument("--method", choices=["wilder", "sma"], default="wilder")
    p_atr.add_argument("--limit", type=int, default=10)

    args = p.parse_args()

    if args.cmd == "ingest":
        cfg = DLIngestConfig(years=args.years)
        ingest(years=cfg.years, gdp_countries=cfg.gdp_countries)
    elif args.cmd == "train":
        train(model=args.model, lookback_days=args.lookback_days, horizon_days=args.horizon_days, asset=str(args.asset), years=int(args.years))
    elif args.cmd == "forecast":
        export_forecast(run_id=int(args.run_id))
    elif args.cmd == "volatility":
        export_gold_daily_sigma(window_days=int(args.window_days), annualize=bool(args.annualize), limit=int(args.limit))
    elif args.cmd == "intraday-sigma":
        intraday_sigma(window_bars=int(args.window_bars), rng=str(args.rng), interval=str(args.interval))
    elif args.cmd == "range-sigma":
        gold_range_sigma(
            years=int(args.years),
            window_days=int(args.window_days),
            use_log=(not bool(args.pct)),
            limit=int(args.limit),
        )
    elif args.cmd == "hilo-z":
        gold_hilo_drop_over_daily_sigma(years=int(args.years), window_days=int(args.window_days), limit=int(args.limit))
    elif args.cmd == "atr":
        gold_atr(years=int(args.years), window_days=int(args.window_days), method=str(args.method), limit=int(args.limit))


if __name__ == "__main__":
    main()
