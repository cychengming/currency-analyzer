"""Backtesting module - Evaluate alert rules on historical data.

Goal:
- Use the same pair naming (e.g., EUR/USD, GOLD/USD)
- Provide a simple, explainable backtest: entry rule + exit rule(s)
- Compute trade PnL and summary stats

Notes:
- Uses daily closes (from modules.currency.fetch_historical_data).
- Entry/exit are evaluated on the close of each day.
- No leverage, fees, or slippage by default.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Trade:
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    pnl_pct: float
    holding_days: int
    exit_reason: str


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _sma(values: List[float], period: int) -> Optional[float]:
    if period is None:
        return None
    period = int(period)
    if period <= 0:
        return None
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _linear_regression_slope_r2(values: List[float]) -> Tuple[Optional[float], Optional[float]]:
    # Same logic style as modules.currency, but kept local to avoid imports.
    if not values or len(values) < 2:
        return (None, None)
    n = len(values)
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    ssxx = 0.0
    ssxy = 0.0
    for i, y in enumerate(values):
        dx = i - x_mean
        dy = y - y_mean
        ssxx += dx * dx
        ssxy += dx * dy
    if ssxx == 0:
        return (None, None)

    slope = ssxy / ssxx
    intercept = y_mean - slope * x_mean

    ss_tot = 0.0
    ss_res = 0.0
    for i, y in enumerate(values):
        y_hat = slope * i + intercept
        ss_tot += (y - y_mean) ** 2
        ss_res += (y - y_hat) ** 2

    if ss_tot == 0:
        r2 = 1.0 if ss_res == 0 else 0.0
    else:
        r2 = 1.0 - (ss_res / ss_tot)
    return (slope, r2)


def _eval_entry_signal(
    entry: Dict[str, Any],
    window_rates: List[float],
    window_dates: List[str],
    window_candles: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """Return True if the entry condition is met on the current day.

    Supported entry types:
    - moving_average_crossover (golden_cross / death_cross)
    - price_level (crosses_above / crosses_below / between)
    - percentage_change (change_threshold over detection_period, optional consistency)
    - long_term_uptrend (combined: % change + MA state + regression)
    """

    etype = (entry.get('type') or entry.get('alert_type') or '').strip()
    if not etype:
        return False

    # --- price level ---
    if etype == 'price_level':
        trigger = (entry.get('trigger_type') or 'crosses_above').strip()
        high = _safe_float(entry.get('price_high'))
        low = _safe_float(entry.get('price_low'))
        if high is not None and low is not None and low > high:
            low, high = high, low
        if len(window_rates) < 2:
            return False
        prev = window_rates[-2]
        cur = window_rates[-1]

        cur_candle = None
        if window_candles and len(window_candles) >= 1:
            cur_candle = window_candles[-1]
        cur_high = _safe_float(cur_candle.get('high')) if isinstance(cur_candle, dict) else None
        cur_low = _safe_float(cur_candle.get('low')) if isinstance(cur_candle, dict) else None

        if trigger == 'crosses_above' and high is not None:
            # Entry evaluated on the day close, but use intraday high if available.
            return prev < high and ((cur_high is not None and cur_high >= high) or cur >= high)
        if trigger == 'crosses_below' and low is not None:
            return prev > low and ((cur_low is not None and cur_low <= low) or cur <= low)
        if trigger == 'between' and high is not None and low is not None:
            return low <= cur <= high
        return False

    # --- moving average crossover ---
    if etype in ('moving_average', 'moving_average_crossover'):
        short_p = int(entry.get('short_ma_period') or entry.get('ma_short_period') or 10)
        long_p = int(entry.get('long_ma_period') or entry.get('ma_long_period') or 50)
        signal = (entry.get('signal_type') or 'golden_cross').strip()
        if long_p <= short_p:
            return False
        if len(window_rates) < long_p + 1:
            return False

        short_today = _sma(window_rates, short_p)
        short_yday = _sma(window_rates[:-1], short_p)
        long_today = _sma(window_rates, long_p)
        long_yday = _sma(window_rates[:-1], long_p)
        if None in (short_today, short_yday, long_today, long_yday):
            return False

        if signal == 'golden_cross':
            return short_yday <= long_yday and short_today > long_today
        if signal == 'death_cross':
            return short_yday >= long_yday and short_today < long_today
        return False

    # --- percentage change trend ---
    if etype in ('percentage_change', 'trend'):
        period = int(entry.get('detection_period') or entry.get('custom_period') or 30)
        threshold = float(entry.get('change_threshold') or entry.get('custom_threshold') or 2.0)
        enable_consistency = bool(entry.get('enable_trend_consistency', True))

        if len(window_rates) < max(2, period):
            return False
        segment = window_rates[-period:]
        old = segment[0]
        new = segment[-1]
        if not old:
            return False
        pct = ((new - old) / old) * 100
        if pct < threshold:
            return False
        if not enable_consistency:
            return True

        recent = segment[-5:] if len(segment) >= 5 else segment
        consistency_ok = all(recent[i] >= recent[i - 1] * 0.998 for i in range(1, len(recent)))
        return consistency_ok

    # --- long term combined uptrend ---
    if etype == 'long_term_uptrend':
        period = int(entry.get('detection_period') or entry.get('custom_period') or 365)
        threshold = float(entry.get('change_threshold') or entry.get('custom_threshold') or 5.0)
        enable_consistency = bool(entry.get('enable_trend_consistency', True))
        short_p = int(entry.get('short_ma_period') or entry.get('ma_short_period') or 50)
        long_p = int(entry.get('long_ma_period') or entry.get('ma_long_period') or 200)

        lookback = max(period, long_p + 2, 60)
        if len(window_rates) < lookback:
            return False

        segment = window_rates[-period:] if len(window_rates) >= period else window_rates
        if len(segment) < 2:
            return False
        old = segment[0]
        new = segment[-1]
        if not old:
            return False
        pct = ((new - old) / old) * 100

        recent = segment[-5:] if len(segment) >= 5 else segment
        consistency_ok = all(recent[i] >= recent[i - 1] * 0.998 for i in range(1, len(recent)))
        pct_ok = pct >= threshold and (consistency_ok if enable_consistency else True)

        short_today = _sma(window_rates, short_p)
        long_today = _sma(window_rates, long_p)
        long_yday = _sma(window_rates[:-1], long_p)
        ma_ok = (short_today is not None and long_today is not None and long_yday is not None and short_today > long_today and long_today >= long_yday)

        slope, r2 = _linear_regression_slope_r2(segment)
        reg_ok = (slope is not None and r2 is not None and slope > 0 and r2 >= 0.25)

        return bool(pct_ok and ma_ok and reg_ok)

    return False


def _eval_exit(
    exit_cfg: Dict[str, Any],
    entry_price: float,
    entry_index: int,
    cur_index: int,
    window_rates: List[float],
) -> Tuple[bool, str, Optional[float]]:
    """Return (should_exit, reason)."""

    cur_price = window_rates[-1]

    # Stop loss / take profit
    stop_loss_pct = _safe_float(exit_cfg.get('stop_loss_pct'))
    take_profit_pct = _safe_float(exit_cfg.get('take_profit_pct'))

    # Evaluate SL/TP using intraday low/high when available.
    cur_low = None
    cur_high = None
    try:
        cur_candle = exit_cfg.get('__cur_candle')
        if isinstance(cur_candle, dict):
            cur_low = _safe_float(cur_candle.get('low'))
            cur_high = _safe_float(cur_candle.get('high'))
    except Exception:
        cur_low = None
        cur_high = None

    stop_level = None
    take_level = None
    if entry_price:
        if stop_loss_pct is not None:
            stop_level = entry_price * (1.0 - abs(stop_loss_pct) / 100.0)
        if take_profit_pct is not None:
            take_level = entry_price * (1.0 + abs(take_profit_pct) / 100.0)

    low_for_checks = cur_low if cur_low is not None else cur_price
    high_for_checks = cur_high if cur_high is not None else cur_price

    hit_stop = (stop_level is not None and low_for_checks <= stop_level)
    hit_take = (take_level is not None and high_for_checks >= take_level)

    # If both are hit on the same day, choose the conservative assumption (stop first).
    if hit_stop and hit_take:
        return (True, 'stop_loss_and_take_profit_same_day', float(stop_level))
    if hit_stop:
        return (True, 'stop_loss', float(stop_level))
    if hit_take:
        return (True, 'take_profit', float(take_level))

    # Time-based exit
    max_holding_days = exit_cfg.get('max_holding_days')
    if max_holding_days is not None:
        try:
            max_holding_days = int(max_holding_days)
        except (TypeError, ValueError):
            max_holding_days = None
    if max_holding_days is not None and max_holding_days > 0:
        if (cur_index - entry_index) >= max_holding_days:
            return (True, 'time_exit', None)

    # Exit signal (optional)
    exit_signal = exit_cfg.get('signal')
    if isinstance(exit_signal, dict) and exit_signal.get('type'):
        if _eval_entry_signal(exit_signal, window_rates, [], None):
            return (True, 'signal_exit', None)

    return (False, '', None)


def _equity_curve_from_trades(trades: List[Trade], initial_capital: float) -> List[float]:
    equity = float(initial_capital)
    curve = [equity]
    for t in trades:
        equity *= (1.0 + (t.pnl_pct / 100.0))
        curve.append(equity)
    return curve


def _max_drawdown(curve: List[float]) -> float:
    if not curve:
        return 0.0
    peak = curve[0]
    max_dd = 0.0
    for v in curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd * 100.0


def run_backtest(
    pair: str,
    days: int,
    entry: Dict[str, Any],
    exit_cfg: Optional[Dict[str, Any]] = None,
    initial_capital: float = 10000.0,
    allow_multiple_trades: bool = True,
) -> Dict[str, Any]:
    """Run a simple backtest and return results suitable for JSON."""

    from modules.currency import fetch_historical_ohlc_data

    exit_cfg = exit_cfg or {}

    series = fetch_historical_ohlc_data(pair, days)
    if not series or len(series) < 5:
        return {
            'success': False,
            'error': 'Not enough historical data',
            'pair': pair,
            'days': days,
            'trades': [],
            'summary': {}
        }

    cleaned_candles: List[Dict[str, Any]] = []
    for d in series:
        dt = d.get('date')
        if not dt:
            continue
        c = _safe_float(d.get('close'))
        if c is None:
            c = _safe_float(d.get('rate'))
        if c is None:
            continue

        o = _safe_float(d.get('open'))
        h = _safe_float(d.get('high'))
        l = _safe_float(d.get('low'))
        # If any are missing, fall back to close.
        o = c if o is None else o
        h = c if h is None else h
        l = c if l is None else l

        cleaned_candles.append({
            'date': str(dt),
            'open': float(o),
            'high': float(h),
            'low': float(l),
            'close': float(c),
        })

    cleaned_dates = [c['date'] for c in cleaned_candles]
    cleaned_rates = [float(c['close']) for c in cleaned_candles]

    if len(cleaned_rates) < 5:
        return {
            'success': False,
            'error': 'Not enough usable data points',
            'pair': pair,
            'days': days,
            'trades': [],
            'summary': {}
        }

    trades: List[Trade] = []

    in_position = False
    entry_price = 0.0
    entry_date = ''
    entry_index = -1

    # Walk forward day-by-day.
    for i in range(1, len(cleaned_rates)):
        window_rates = cleaned_rates[: i + 1]
        window_dates = cleaned_dates[: i + 1]
        window_candles = cleaned_candles[: i + 1]

        if not in_position:
            if _eval_entry_signal(entry, window_rates, window_dates, window_candles):
                in_position = True
                entry_price = window_rates[-1]
                entry_date = window_dates[-1]
                entry_index = i
        else:
            # Pass the current candle to exit logic via a private key to avoid signature churn.
            exit_cfg_local = dict(exit_cfg)
            exit_cfg_local['__cur_candle'] = window_candles[-1]
            should_exit, reason, fill_price = _eval_exit(exit_cfg_local, entry_price, entry_index, i, window_rates)
            if should_exit:
                exit_price = float(fill_price) if fill_price is not None else float(window_rates[-1])
                exit_date = window_dates[-1]
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price else 0.0
                trades.append(
                    Trade(
                        entry_date=entry_date,
                        entry_price=round(entry_price, 6),
                        exit_date=exit_date,
                        exit_price=round(exit_price, 6),
                        pnl_pct=round(pnl_pct, 4),
                        holding_days=int(i - entry_index),
                        exit_reason=reason or 'exit',
                    )
                )
                in_position = False

                if not allow_multiple_trades:
                    break

    # If still in position, close at last price
    if in_position:
        exit_price = float(cleaned_rates[-1])
        exit_date = cleaned_dates[-1]
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price else 0.0
        trades.append(
            Trade(
                entry_date=entry_date,
                entry_price=round(entry_price, 6),
                exit_date=exit_date,
                exit_price=round(exit_price, 6),
                pnl_pct=round(pnl_pct, 4),
                holding_days=int((len(cleaned_rates) - 1) - entry_index),
                exit_reason='end_of_data',
            )
        )

    # Summary
    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct <= 0]

    equity = _equity_curve_from_trades(trades, initial_capital)
    total_return_pct = ((equity[-1] - initial_capital) / initial_capital) * 100 if initial_capital else 0.0

    avg_pnl = sum(t.pnl_pct for t in trades) / len(trades) if trades else 0.0
    win_rate = (len(wins) / len(trades) * 100) if trades else 0.0
    max_dd = _max_drawdown(equity)

    return {
        'success': True,
        'pair': pair,
        'days': days,
        'entry': entry,
        'exit': exit_cfg,
        'initial_capital': float(initial_capital),
        'trades': [asdict(t) for t in trades],
        'summary': {
            'num_trades': len(trades),
            'win_rate_pct': round(win_rate, 2),
            'avg_trade_pnl_pct': round(avg_pnl, 4),
            'total_return_pct': round(total_return_pct, 2),
            'final_equity': round(equity[-1], 2),
            'max_drawdown_pct': round(max_dd, 2),
        }
    }
