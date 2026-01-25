"""Currency data module - Fetch and analyze exchange rates.

This project primarily monitors FX pairs via frankfurter.app.
It also supports a small set of commodities via public sources.

Note: Yahoo Finance may return 401/blocked in some environments (including
some Docker networks). In that case we fall back to Stooq (free, no API key).
"""

import requests
from datetime import datetime, timedelta
import time
from urllib.parse import urlencode


# Commodity pairs are represented as BASE/USD (e.g., GOLD/USD).
# Backed by futures symbols.
COMMODITY_SYMBOLS = {
    'GOLD/USD': 'GC=F',
    'SILVER/USD': 'SI=F',
    'COPPER/USD': 'HG=F',
    'WHEAT/USD': 'ZW=F',
    'SOYBEAN/USD': 'ZS=F',
    'CORN/USD': 'ZC=F',
}

# Stooq symbols (free, no key). These are typically delayed end-of-day or delayed quotes.
COMMODITY_STOOQ_SYMBOLS = {
    'GOLD/USD': 'gc.f',
    'SILVER/USD': 'si.f',
    'COPPER/USD': 'hg.f',
    'WHEAT/USD': 'zw.f',
    'SOYBEAN/USD': 'zs.f',
    'CORN/USD': 'zc.f',
}


# Yahoo Finance quote endpoint is sometimes blocked (401) from containers.
# If we detect that, we disable Yahoo quotes and rely on Stooq.
_YAHOO_QUOTES_BLOCKED = False


def is_commodity_pair(pair: str) -> bool:
    return pair in COMMODITY_SYMBOLS

def parse_pair(pair):
    """Split currency pair"""
    return pair.split('/')


def _fetch_yahoo_quotes(symbols):
    """Fetch live quote data from Yahoo Finance for multiple symbols."""
    if not symbols:
        return {}
    url = 'https://query1.finance.yahoo.com/v7/finance/quote'
    resp = requests.get(
        url,
        params={'symbols': ','.join(symbols)},
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json() or {}
    results = (payload.get('quoteResponse') or {}).get('result') or []
    by_symbol = {}
    for item in results:
        sym = item.get('symbol')
        if sym:
            by_symbol[sym] = item
    return by_symbol


def _fetch_stooq_quotes(symbols):
    """Fetch live-ish quotes from Stooq (CSV, no API key).

    Example: https://stooq.com/q/l/?s=gc.f,si.f&f=sd2t2ohlcv&h&e=csv
    """
    if not symbols:
        return {}
    # Stooq's q/l endpoint is inconsistent for multi-symbol queries (it may return
    # a single malformed row). For reliability, fetch each symbol individually.
    out = {}

    for symbol in symbols:
        try:
            qs = urlencode({'s': symbol, 'f': 'sd2t2ohlcv', 'e': 'csv'})
            url = 'https://stooq.com/q/l/?' + qs + '&h'
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            resp.raise_for_status()
            text = resp.text or ''
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if len(lines) < 2:
                continue

            header = [h.strip().lower() for h in lines[0].split(',')]
            parts = [p.strip() for p in lines[1].split(',')]
            if len(parts) != len(header):
                continue

            row = dict(zip(header, parts))
            sym = (row.get('symbol') or '').lower()
            if sym:
                out[sym] = row
        except Exception:
            continue

    return out


def _fetch_yahoo_history(symbol: str, days: int):
    """Fetch daily historical closes for `days` from Yahoo Finance chart API."""
    days = int(days) if days is not None else 30
    if days <= 0:
        return []

    # Yahoo's chart API expects a limited set of ranges.
    # Using large "Xd" values (e.g., 360d/720d) can yield surprising defaults.
    # Map to supported ranges so UI selections like 12/24 months behave correctly.
    # Common supported values: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    if days >= 365 * 10:
        rng = '10y'
    elif days >= 365 * 5:
        rng = '5y'
    elif days >= 700:  # ~24 months (UI uses months*30 => 24m = 720d)
        rng = '2y'
    elif days >= 350:  # ~12 months (UI uses months*30 => 12m = 360d)
        rng = '1y'
    elif days >= 180:
        rng = '6mo'
    elif days >= 90:
        rng = '3mo'
    elif days >= 30:
        rng = '1mo'
    else:
        rng = str(days) + 'd'

    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    resp = requests.get(
        url,
        params={'range': rng, 'interval': '1d'},
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json() or {}
    chart = (payload.get('chart') or {}).get('result')
    if not chart:
        return []

    result = chart[0] or {}
    ts_list = result.get('timestamp') or []
    quote = ((result.get('indicators') or {}).get('quote') or [{}])[0] or {}
    closes = quote.get('close') or []

    out = []
    for ts, close in zip(ts_list, closes):
        if close is None:
            continue
        try:
            date_str = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
        except Exception:
            continue
        out.append({'date': date_str, 'rate': float(close)})
    return out


def _fetch_yahoo_history_ohlc(symbol: str, days: int):
    """Fetch daily OHLC for `days` from Yahoo Finance chart API."""
    days = int(days) if days is not None else 30
    if days <= 0:
        return []

    if days >= 365 * 10:
        rng = '10y'
    elif days >= 365 * 5:
        rng = '5y'
    elif days >= 700:
        rng = '2y'
    elif days >= 350:
        rng = '1y'
    elif days >= 180:
        rng = '6mo'
    elif days >= 90:
        rng = '3mo'
    elif days >= 30:
        rng = '1mo'
    else:
        rng = str(days) + 'd'

    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    resp = requests.get(
        url,
        params={'range': rng, 'interval': '1d'},
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json() or {}
    chart = (payload.get('chart') or {}).get('result')
    if not chart:
        return []

    result = chart[0] or {}
    ts_list = result.get('timestamp') or []
    quote = ((result.get('indicators') or {}).get('quote') or [{}])[0] or {}

    opens = quote.get('open') or []
    highs = quote.get('high') or []
    lows = quote.get('low') or []
    closes = quote.get('close') or []

    out = []
    for ts, o, h, l, c in zip(ts_list, opens, highs, lows, closes):
        if c is None:
            continue
        try:
            date_str = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
        except Exception:
            continue

        # Yahoo sometimes returns None for O/H/L on some days; fall back to close.
        try:
            c_f = float(c)
        except (TypeError, ValueError):
            continue

        def _num_or_close(x):
            try:
                return float(x)
            except (TypeError, ValueError):
                return c_f

        o_f = _num_or_close(o)
        h_f = _num_or_close(h)
        l_f = _num_or_close(l)

        out.append({
            'date': date_str,
            'open': o_f,
            'high': h_f,
            'low': l_f,
            'close': c_f,
            'rate': c_f,
        })
    return out


def _fetch_yahoo_last_two_daily_closes(symbol: str):
    """Fetch the last two available daily closes from Yahoo Finance chart API.

    This endpoint is often accessible even when the Yahoo quote endpoint is blocked.
    """
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    resp = requests.get(
        url,
        params={'range': '10d', 'interval': '1d'},
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json() or {}
    chart = (payload.get('chart') or {}).get('result')
    if not chart:
        return (None, None)

    result = chart[0] or {}
    quote = ((result.get('indicators') or {}).get('quote') or [{}])[0] or {}
    closes = quote.get('close') or []

    # keep only numeric closes
    cleaned = []
    for c in closes:
        if c is None:
            continue
        try:
            cleaned.append(float(c))
        except (TypeError, ValueError):
            continue

    if not cleaned:
        return (None, None)

    last = cleaned[-1]
    prev = cleaned[-2] if len(cleaned) >= 2 else None
    return (last, prev)


def _fetch_stooq_history(symbol: str, days: int):
    """Fetch daily OHLC from Stooq and return recent closes."""
    days = int(days) if days is not None else 30
    if days <= 0:
        return []

    url = 'https://stooq.com/q/d/l/'
    resp = requests.get(
        url,
        params={'s': symbol, 'i': 'd'},
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=10,
    )
    resp.raise_for_status()

    text = resp.text or ''
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []

    header = [h.strip().lower() for h in lines[0].split(',')]
    idx_date = header.index('date') if 'date' in header else None
    idx_close = header.index('close') if 'close' in header else None
    if idx_date is None or idx_close is None:
        return []

    rows = []
    for ln in lines[1:]:
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) <= max(idx_date, idx_close):
            continue
        date_str = parts[idx_date]
        close_str = parts[idx_close]
        try:
            close_val = float(close_str)
        except (TypeError, ValueError):
            continue
        rows.append({'date': date_str, 'rate': close_val})

    if not rows:
        return []
    # Keep only the most recent `days` rows
    return rows[-days:]


def _fetch_stooq_history_ohlc(symbol: str, days: int):
    """Fetch daily OHLC from Stooq and return recent OHLC bars."""
    days = int(days) if days is not None else 30
    if days <= 0:
        return []

    url = 'https://stooq.com/q/d/l/'
    resp = requests.get(
        url,
        params={'s': symbol, 'i': 'd'},
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=10,
    )
    resp.raise_for_status()

    text = resp.text or ''
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []

    header = [h.strip().lower() for h in lines[0].split(',')]
    need = ['date', 'open', 'high', 'low', 'close']
    idx = {k: (header.index(k) if k in header else None) for k in need}
    if any(idx[k] is None for k in need):
        return []

    rows = []
    for ln in lines[1:]:
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) <= max(idx.values()):
            continue

        date_str = parts[idx['date']]
        try:
            o = float(parts[idx['open']])
            h = float(parts[idx['high']])
            l = float(parts[idx['low']])
            c = float(parts[idx['close']])
        except (TypeError, ValueError):
            continue

        rows.append({
            'date': date_str,
            'open': o,
            'high': h,
            'low': l,
            'close': c,
            'rate': c,
        })

    if not rows:
        return []
    return rows[-days:]


def fetch_historical_ohlc_data(pair, days):
    """Fetch historical OHLC data for a pair.

    - Commodities: uses Yahoo OHLC when available; falls back to Stooq OHLC.
    - FX (Frankfurter): does not provide OHLC, so we synthesize OHLC from the daily rate.
    """
    try:
        if is_commodity_pair(pair):
            symbol = COMMODITY_SYMBOLS.get(pair)
            if symbol:
                try:
                    data = _fetch_yahoo_history_ohlc(symbol, days)
                    if data:
                        return data
                except Exception as e:
                    print('Error fetching commodity OHLC (Yahoo): ' + str(e))

            stooq_symbol = COMMODITY_STOOQ_SYMBOLS.get(pair)
            if not stooq_symbol:
                return []
            try:
                data = _fetch_stooq_history_ohlc(stooq_symbol, days)
                if data:
                    return data
            except Exception as e:
                print('Error fetching commodity OHLC (Stooq): ' + str(e))
                return []

            # Last-resort: synthesize OHLC from closes
            try:
                close_series = fetch_historical_data(pair, days)
                out = []
                for d in close_series:
                    dt = d.get('date')
                    c = d.get('rate')
                    try:
                        c = float(c)
                    except (TypeError, ValueError):
                        continue
                    out.append({'date': dt, 'open': c, 'high': c, 'low': c, 'close': c, 'rate': c})
                return out
            except Exception:
                return []

        # FX: Prefer Yahoo OHLC (real OHLC). If unavailable, synthesize from Frankfurter close.
        try:
            base, quote = parse_pair(pair)
            fx_symbol = f'{base}{quote}=X'
            yahoo = _fetch_yahoo_history_ohlc(fx_symbol, days)
            if yahoo:
                return yahoo
        except Exception as e:
            print('Error fetching FX OHLC (Yahoo): ' + str(e))

        # FX: Frankfurter provides a single daily rate (close). Synthesize OHLC.
        series = fetch_historical_data(pair, days)
        out = []
        for d in series:
            dt = d.get('date')
            rate = d.get('rate')
            try:
                c = float(rate)
            except (TypeError, ValueError):
                continue
            out.append({
                'date': dt,
                'open': c,
                'high': c,
                'low': c,
                'close': c,
                'rate': c,
            })
        return out
    except Exception as e:
        print('Error fetching historical OHLC data for ' + str(pair) + ': ' + str(e))
        return []


def _fetch_frankfurter_rates_for_date(date_str: str, to_list: str):
    """Fetch USD->X rates for a specific date from Frankfurter.

    Returns dict of rates, or None if not available.
    """
    try:
        resp = requests.get(
            'https://api.frankfurter.app/' + date_str,
            params={'from': 'USD', 'to': to_list},
            timeout=10,
        )
        if not resp.ok:
            return None
        payload = resp.json() or {}
        rates = payload.get('rates') or {}
        return rates if isinstance(rates, dict) and rates else None
    except Exception:
        return None

def fetch_live_rates(currency_pairs):
    """Fetch current exchange rates"""
    try:
        currency_pairs = list(currency_pairs or [])

        commodity_pairs = [p for p in currency_pairs if is_commodity_pair(p)]
        fx_pairs = [p for p in currency_pairs if not is_commodity_pair(p)]

        rates = {}

        def calculate_change(today_rate, yesterday_rate):
            if not yesterday_rate:
                return {'change': 0, 'changePercent': 0}
            change = today_rate - yesterday_rate
            change_percent = (change / yesterday_rate) * 100
            return {'change': change, 'changePercent': change_percent}

        # ---- Commodities (Yahoo Finance with Stooq fallback) ----
        # Important: do not let commodity fetch failures prevent FX rates from loading.
        if commodity_pairs:
            filled_pairs = set()

            # 1) Try Yahoo
            global _YAHOO_QUOTES_BLOCKED
            if not _YAHOO_QUOTES_BLOCKED:
                try:
                    symbols = [COMMODITY_SYMBOLS[p] for p in commodity_pairs]
                    quote_map = _fetch_yahoo_quotes(symbols)
                    for pair in commodity_pairs:
                        sym = COMMODITY_SYMBOLS[pair]
                        q = quote_map.get(sym) or {}
                        price = q.get('regularMarketPrice')
                        prev = q.get('regularMarketPreviousClose')
                        chg = q.get('regularMarketChange')
                        chg_pct = q.get('regularMarketChangePercent')

                        # Fallback calculations if Yahoo didn't provide change fields
                        if chg is None and price is not None and prev not in (None, 0):
                            chg = price - prev
                        if chg_pct is None and price is not None and prev not in (None, 0):
                            chg_pct = (chg / prev) * 100 if chg is not None else 0

                        if price is None:
                            continue

                        rates[pair] = {
                            'rate': round(float(price), 4),
                            'change': round(float(chg or 0), 4),
                            'changePercent': round(float(chg_pct or 0), 2)
                        }
                        filled_pairs.add(pair)
                except Exception as e:
                    msg = str(e)
                    # Stop spamming and stop retrying if Yahoo is blocked.
                    if '401' in msg:
                        _YAHOO_QUOTES_BLOCKED = True
                    print('Error fetching commodity rates (Yahoo): ' + msg)

            # 2) Fallback to Stooq for missing pairs
            remaining = [p for p in commodity_pairs if p not in filled_pairs]

            # 2a) If Yahoo quotes are blocked, try Yahoo chart (daily closes)
            if remaining:
                try:
                    for pair in list(remaining):
                        symbol = COMMODITY_SYMBOLS.get(pair)
                        if not symbol:
                            continue
                        last, prev = _fetch_yahoo_last_two_daily_closes(symbol)
                        if last is None:
                            continue
                        chg = (last - prev) if (prev not in (None, 0)) else 0.0
                        chg_pct = (chg / prev * 100) if (prev not in (None, 0)) else 0.0
                        rates[pair] = {
                            'rate': round(float(last), 4),
                            'change': round(float(chg), 4),
                            'changePercent': round(float(chg_pct), 2)
                        }
                        filled_pairs.add(pair)
                except Exception as e:
                    print('Error fetching commodity rates (Yahoo chart): ' + str(e))

            remaining = [p for p in commodity_pairs if p not in filled_pairs]
            if remaining:
                try:
                    stooq_symbols = [COMMODITY_STOOQ_SYMBOLS[p] for p in remaining if p in COMMODITY_STOOQ_SYMBOLS]
                    stooq_map = _fetch_stooq_quotes(stooq_symbols)

                    def to_float(v):
                        try:
                            return float(v)
                        except (TypeError, ValueError):
                            return None

                    for pair in remaining:
                        sym = COMMODITY_STOOQ_SYMBOLS.get(pair)
                        if not sym:
                            continue
                        row = stooq_map.get(sym.lower()) or {}
                        close = to_float(row.get('close'))
                        open_ = to_float(row.get('open'))
                        if close is None:
                            continue

                        chg = (close - open_) if (open_ not in (None, 0)) else 0.0
                        chg_pct = (chg / open_ * 100) if (open_ not in (None, 0)) else 0.0

                        rates[pair] = {
                            'rate': round(float(close), 4),
                            'change': round(float(chg or 0), 4),
                            'changePercent': round(float(chg_pct or 0), 2)
                        }
                except Exception as e:
                    print('Error fetching commodity rates (Stooq): ' + str(e))

        # ---- FX (Frankfurter) ----
        if fx_pairs:
            try:
                # Collect all currencies we need USD->X for
                needed = set()
                for pair in fx_pairs:
                    parts = parse_pair(pair)
                    if len(parts) != 2:
                        continue
                    base, quote = parts
                    if base and base != 'USD':
                        needed.add(base)
                    if quote and quote != 'USD':
                        needed.add(quote)

                to_list = ','.join(sorted(needed))
                response = requests.get('https://api.frankfurter.app/latest', params={'from': 'USD', 'to': to_list}, timeout=10)
                response.raise_for_status()
                today_data = response.json() or {}
                today_rates = (today_data.get('rates') or {})

                # Find the most recent prior date with rates (weekends/holidays return no data).
                y_rates = {}
                # Use Frankfurter's reported date for "latest" (may be a prior business day).
                base_date_str = today_data.get('date')
                try:
                    base_date = datetime.strptime(base_date_str, '%Y-%m-%d') if base_date_str else datetime.now()
                except Exception:
                    base_date = datetime.now()

                for back in range(1, 11):
                    d = (base_date - timedelta(days=back)).strftime('%Y-%m-%d')
                    found = _fetch_frankfurter_rates_for_date(d, to_list)
                    if found:
                        y_rates = found
                        break

                def num_or_none(v):
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return None

                for pair in fx_pairs:
                    parts = parse_pair(pair)
                    if len(parts) != 2:
                        continue
                    base, quote = parts

                    today_rate = None
                    yesterday_rate = None

                    # USD/X
                    if base == 'USD':
                        today_rate = num_or_none(today_rates.get(quote))
                        yesterday_rate = num_or_none(y_rates.get(quote)) if quote in y_rates else today_rate

                    # X/USD
                    elif quote == 'USD':
                        inv_today = num_or_none(today_rates.get(base))
                        inv_y = num_or_none(y_rates.get(base)) if base in y_rates else inv_today
                        if inv_today:
                            today_rate = 1 / inv_today
                        if inv_y:
                            yesterday_rate = 1 / inv_y
                        if yesterday_rate is None:
                            yesterday_rate = today_rate

                    # Cross rates via USD
                    else:
                        usd_to_quote = num_or_none(today_rates.get(quote))
                        usd_to_base = num_or_none(today_rates.get(base))
                        usd_to_quote_y = num_or_none(y_rates.get(quote)) if quote in y_rates else usd_to_quote
                        usd_to_base_y = num_or_none(y_rates.get(base)) if base in y_rates else usd_to_base
                        if usd_to_quote is not None and usd_to_base:
                            today_rate = usd_to_quote / usd_to_base
                        if usd_to_quote_y is not None and usd_to_base_y:
                            yesterday_rate = usd_to_quote_y / usd_to_base_y
                        if yesterday_rate is None:
                            yesterday_rate = today_rate

                    if today_rate is None:
                        continue

                    change_data = calculate_change(today_rate, yesterday_rate)
                    rates[pair] = {
                        'rate': round(today_rate, 4),
                        'change': round(change_data['change'], 4),
                        'changePercent': round(change_data['changePercent'], 2)
                    }
            except Exception as e:
                print('Error fetching FX rates: ' + str(e))
        return rates
    except Exception as e:
        print("Error fetching live rates: " + str(e))
        return {}

def fetch_historical_data(pair, days):
    """Fetch historical data for a currency pair"""
    try:
        if is_commodity_pair(pair):
            # Try Yahoo first, then fall back to Stooq.
            symbol = COMMODITY_SYMBOLS.get(pair)
            if symbol:
                try:
                    return _fetch_yahoo_history(symbol, days)
                except Exception as e:
                    print('Error fetching commodity history (Yahoo): ' + str(e))

            stooq_symbol = COMMODITY_STOOQ_SYMBOLS.get(pair)
            if not stooq_symbol:
                return []
            try:
                return _fetch_stooq_history(stooq_symbol, days)
            except Exception as e:
                print('Error fetching commodity history (Stooq): ' + str(e))
                return []

        base, quote = parse_pair(pair)

        # Frankfurter (primary for FX)
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')

            url = 'https://api.frankfurter.app/' + start_str + '..' + end_str + '?from=' + base + '&to=' + quote
            time.sleep(0.1)  # Rate limiting

            response = None
            last_error = None
            for _ in range(2):
                try:
                    response = requests.get(url, timeout=12)
                    response.raise_for_status()
                    last_error = None
                    break
                except Exception as e:
                    last_error = e

            if response is None or last_error is not None:
                raise last_error or Exception('Frankfurter request failed')

            data = response.json()

            chart_data = []
            for date_str, rates in sorted(data.get('rates', {}).items()):
                chart_data.append({
                    'date': date_str,
                    'rate': rates[quote]
                })

            if chart_data:
                return chart_data
        except Exception as e:
            print('Error fetching FX history (Frankfurter): ' + str(e))

        # Fallback: Yahoo chart for FX (often accessible even when Frankfurter is slow/unreachable)
        try:
            fx_symbol = f'{base}{quote}=X'
            return _fetch_yahoo_history(fx_symbol, days)
        except Exception as e:
            print('Error fetching FX history (Yahoo): ' + str(e))
            return []
    except Exception as e:
        print("Error fetching historical data for " + pair + ": " + str(e))
        return []

def detect_trend(pair, currency_pairs):
    """Detect if currency pair shows uptrend"""
    from modules.database import get_alert_preference, get_setting
    
    try:
        # Get pair-specific settings or use defaults
        pref = get_alert_preference(pair)
        if not pref['enabled']:
            return None
        
        detection_period = pref['custom_period'] or int(get_setting('detection_period', 30))
        trend_threshold = pref['custom_threshold'] or float(get_setting('trend_threshold', 2.0))
        
        data = fetch_historical_data(pair, detection_period)
        
        if not data or len(data) < 2:
            return None
        
        oldest_rate = data[0]['rate']
        newest_rate = data[-1]['rate']
        percent_change = ((newest_rate - oldest_rate) / oldest_rate) * 100
        
        # Check for consistent uptrend
        recent_data = data[-5:] if len(data) >= 5 else data
        is_consistent = all(
            recent_data[i]['rate'] >= recent_data[i-1]['rate'] * 0.998
            for i in range(1, len(recent_data))
        )
        
        is_trending = percent_change >= trend_threshold and is_consistent
        
        return {
            'is_trending': is_trending,
            'percent_change': round(percent_change, 2),
            'old_rate': round(oldest_rate, 4),
            'new_rate': round(newest_rate, 4),
            'start_date': data[0]['date'],
            'end_date': data[-1]['date']
        }
    except Exception as e:
        print("Error detecting trend for " + pair + ": " + str(e))
        return None
def detect_historical_high(pair, currency_pairs, lookback_years=5):
    """Detect if currency is at historical high"""
    try:
        from modules.database import get_alert_preference
        
        pref = get_alert_preference(pair)
        if not pref['enabled']:
            return None
        
        days_lookback = lookback_years * 365
        data = fetch_historical_data(pair, days_lookback)
        
        if not data or len(data) < 2:
            return None
        
        current_rate = data[-1]['rate']
        max_rate = max([d['rate'] for d in data])
        min_rate = min([d['rate'] for d in data])
        
        is_high = abs(current_rate - max_rate) < max_rate * 0.001  # Within 0.1%
        
        return {
            'is_high': is_high,
            'current_rate': round(current_rate, 4),
            'max_rate': round(max_rate, 4),
            'min_rate': round(min_rate, 4),
            'proximity_percent': round(((current_rate - min_rate) / (max_rate - min_rate)) * 100, 2),
            'lookback_years': lookback_years
        }
    except Exception as e:
        print("Error detecting historical high for " + pair + ": " + str(e))
        return None

def detect_historical_low(pair, currency_pairs, lookback_years=5):
    """Detect if currency is at historical low"""
    try:
        from modules.database import get_alert_preference
        
        pref = get_alert_preference(pair)
        if not pref['enabled']:
            return None
        
        days_lookback = lookback_years * 365
        data = fetch_historical_data(pair, days_lookback)
        
        if not data or len(data) < 2:
            return None
        
        current_rate = data[-1]['rate']
        max_rate = max([d['rate'] for d in data])
        min_rate = min([d['rate'] for d in data])
        
        is_low = abs(current_rate - min_rate) < min_rate * 0.001  # Within 0.1%
        
        return {
            'is_low': is_low,
            'current_rate': round(current_rate, 4),
            'max_rate': round(max_rate, 4),
            'min_rate': round(min_rate, 4),
            'proximity_percent': round(((current_rate - min_rate) / (max_rate - min_rate)) * 100, 2),
            'lookback_years': lookback_years
        }
    except Exception as e:
        print("Error detecting historical low for " + pair + ": " + str(e))
        return None

def detect_price_level_cross(pair, currency_pairs, price_high=None, price_low=None, trigger_type='crosses_above'):
    """Detect if price crosses defined levels"""
    try:
        from modules.database import get_alert_preference
        
        pref = get_alert_preference(pair)
        if not pref['enabled']:
            return None
        
        data = fetch_historical_data(pair, 7)  # Check last 7 days
        
        if not data or len(data) < 2:
            return None
        
        current_rate = data[-1]['rate']
        previous_rate = data[-2]['rate']

        # Normalize inputs (handle strings/nulls)
        try:
            price_high = float(price_high) if price_high is not None else None
        except (TypeError, ValueError):
            price_high = None
        try:
            price_low = float(price_low) if price_low is not None else None
        except (TypeError, ValueError):
            price_low = None

        if trigger_type is not None:
            trigger_type = str(trigger_type).strip()

        if not trigger_type:
            if price_high is not None and price_low is not None:
                trigger_type = 'between'
            else:
                trigger_type = 'crosses_above'

        if price_high is not None and price_low is not None and price_low > price_high:
            price_low, price_high = price_high, price_low
        
        is_triggered = False
        has_high = price_high is not None
        has_low = price_low is not None
        if trigger_type == 'crosses_above' and has_high:
            is_triggered = previous_rate < price_high and current_rate >= price_high
        elif trigger_type == 'crosses_below' and has_low:
            is_triggered = previous_rate > price_low and current_rate <= price_low
        elif trigger_type == 'between' and has_high and has_low:
            is_triggered = price_low <= current_rate <= price_high
        
        return {
            'is_triggered': is_triggered,
            'current_rate': round(current_rate, 4),
            'price_high': price_high,
            'price_low': price_low,
            'trigger_type': trigger_type
        }
    except Exception as e:
        print("Error detecting price level cross for " + pair + ": " + str(e))
        return None

def detect_volatility_spike(pair, currency_pairs, lookback_period=30, volatility_type='high'):
    """Detect if volatility exceeds normal ranges"""
    try:
        from modules.database import get_alert_preference
        import math
        
        pref = get_alert_preference(pair)
        if not pref['enabled']:
            return None
        
        data = fetch_historical_data(pair, lookback_period + 30)
        
        if not data or len(data) < lookback_period:
            return None
        
        # Calculate returns
        recent_data = data[-lookback_period:]
        recent_returns = [
            ((recent_data[i]['rate'] - recent_data[i-1]['rate']) / recent_data[i-1]['rate']) * 100
            for i in range(1, len(recent_data))
        ]
        
        # Calculate standard deviation (volatility)
        mean_return = sum(recent_returns) / len(recent_returns)
        variance = sum([(r - mean_return) ** 2 for r in recent_returns]) / len(recent_returns)
        current_volatility = math.sqrt(variance)
        
        # Compare to historical volatility
        older_data = data[:-lookback_period]
        older_returns = [
            ((older_data[i]['rate'] - older_data[i-1]['rate']) / older_data[i-1]['rate']) * 100
            for i in range(1, len(older_data))
        ]
        mean_old = sum(older_returns) / len(older_returns)
        variance_old = sum([(r - mean_old) ** 2 for r in older_returns]) / len(older_returns)
        avg_volatility = math.sqrt(variance_old)
        
        vol_ratio = current_volatility / avg_volatility if avg_volatility > 0 else 0
        is_spike = (volatility_type == 'high' and vol_ratio > 2.0) or (volatility_type == 'low' and vol_ratio < 0.5)
        
        return {
            'is_spike': is_spike,
            'current_volatility': round(current_volatility, 4),
            'average_volatility': round(avg_volatility, 4),
            'volatility_ratio': round(vol_ratio, 2),
            'volatility_type': volatility_type
        }
    except Exception as e:
        print("Error detecting volatility for " + pair + ": " + str(e))
        return None

def detect_moving_average_crossover(pair, currency_pairs, short_period=10, long_period=50, signal_type='golden_cross'):
    """Detect moving average crossovers"""
    try:
        from modules.database import get_alert_preference
        
        pref = get_alert_preference(pair)
        if not pref['enabled']:
            return None
        
        # Need data for both periods + 1 day to detect crossover
        lookback = long_period + 1
        data = fetch_historical_data(pair, lookback)
        
        if not data or len(data) < long_period:
            return None
        
        rates = [d['rate'] for d in data]
        
        # Calculate short MA
        short_ma_today = sum(rates[-short_period:]) / short_period
        short_ma_yesterday = sum(rates[-short_period-1:-1]) / short_period if len(rates) > short_period else short_ma_today
        
        # Calculate long MA
        long_ma_today = sum(rates[-long_period:]) / long_period
        long_ma_yesterday = sum(rates[-long_period-1:-1]) / long_period if len(rates) > long_period else long_ma_today
        
        is_crossover = False
        if signal_type == 'golden_cross':
            is_crossover = short_ma_yesterday <= long_ma_yesterday and short_ma_today > long_ma_today
        elif signal_type == 'death_cross':
            is_crossover = short_ma_yesterday >= long_ma_yesterday and short_ma_today < long_ma_today
        
        return {
            'is_crossover': is_crossover,
            'short_ma': round(short_ma_today, 4),
            'long_ma': round(long_ma_today, 4),
            'current_rate': round(rates[-1], 4),
            'signal_type': signal_type,
            'short_period': short_period,
            'long_period': long_period
        }
    except Exception as e:
        print("Error detecting MA crossover for " + pair + ": " + str(e))
        return None


def _linear_regression_slope_r2(values):
    """Return (slope, r2) for y over x=0..n-1.

    Implemented without numpy to keep dependencies simple.
    """
    if not values:
        return (None, None)
    n = len(values)
    if n < 2:
        return (None, None)

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


def detect_long_term_uptrend(pair, currency_pairs):
    """Detect long-term upside trend by combining multiple confirmations.

    Combines:
    - percent change over a period (with optional consistency check)
    - bullish MA state (short MA above long MA, long MA rising)
    - positive linear regression slope with minimum R^2
    """
    from modules.database import get_alert_preference, get_setting

    try:
        pref = get_alert_preference(pair)
        if not pref['enabled']:
            return None

        detection_period = pref['custom_period'] or int(get_setting('detection_period', 30))
        change_threshold = pref['custom_threshold'] or float(get_setting('trend_threshold', 2.0))
        enable_trend_consistency = bool(pref.get('enable_trend_consistency', True))

        ma_short = int(pref.get('ma_short_period') or 50)
        ma_long = int(pref.get('ma_long_period') or 200)

        # Require enough data for MA + a reasonable regression.
        lookback = max(int(detection_period), int(ma_long) + 2, 60)
        data = fetch_historical_data(pair, lookback)
        if not data or len(data) < 2:
            return None

        rates_all = [d['rate'] for d in data if d.get('rate') is not None]
        if len(rates_all) < 2:
            return None

        # Use the most recent window for trend/regression.
        window = rates_all[-min(len(rates_all), int(detection_period)):] if detection_period else rates_all
        if len(window) < 2:
            return None

        oldest_rate = window[0]
        newest_rate = window[-1]
        if not oldest_rate:
            return None

        percent_change = ((newest_rate - oldest_rate) / oldest_rate) * 100

        # Consistency (same style as detect_trend)
        recent_window = window[-5:] if len(window) >= 5 else window
        consistency_ok = all(
            recent_window[i] >= recent_window[i - 1] * 0.998
            for i in range(1, len(recent_window))
        )

        pct_ok = percent_change >= float(change_threshold)
        if enable_trend_consistency:
            pct_ok = pct_ok and consistency_ok

        # MA state (not just a one-time crossover event)
        ma_ok = False
        short_ma_today = None
        long_ma_today = None
        long_ma_yesterday = None
        if len(rates_all) >= max(ma_long, ma_short) + 1 and ma_short >= 2 and ma_long > ma_short:
            short_ma_today = sum(rates_all[-ma_short:]) / ma_short
            long_ma_today = sum(rates_all[-ma_long:]) / ma_long
            long_ma_yesterday = sum(rates_all[-ma_long - 1:-1]) / ma_long
            ma_ok = (short_ma_today > long_ma_today) and (long_ma_today >= long_ma_yesterday)

        # Regression confirmation
        reg_slope, reg_r2 = _linear_regression_slope_r2(window)
        reg_ok = False
        slope_pct = None
        if reg_slope is not None and reg_r2 is not None and oldest_rate not in (None, 0):
            slope_pct = (reg_slope * (len(window) - 1) / oldest_rate) * 100
            # R2 threshold tuned to avoid random noise calling it a trend
            reg_ok = (reg_slope > 0) and (reg_r2 >= 0.25)

        is_uptrend = bool(pct_ok and ma_ok and reg_ok)

        return {
            'is_trending': is_uptrend,
            'percent_change': round(percent_change, 2),
            'old_rate': round(oldest_rate, 4),
            'new_rate': round(newest_rate, 4),
            'start_date': data[-len(window)]['date'] if len(data) >= len(window) else data[0].get('date'),
            'end_date': data[-1].get('date'),
            'enable_trend_consistency': enable_trend_consistency,
            'consistency_ok': bool(consistency_ok),
            'pct_ok': bool(pct_ok),
            'ma_ok': bool(ma_ok),
            'short_ma': round(short_ma_today, 4) if short_ma_today is not None else None,
            'long_ma': round(long_ma_today, 4) if long_ma_today is not None else None,
            'reg_ok': bool(reg_ok),
            'reg_r2': round(reg_r2, 3) if reg_r2 is not None else None,
            'reg_slope_pct': round(slope_pct, 2) if slope_pct is not None else None,
        }
    except Exception as e:
        print("Error detecting long-term uptrend for " + pair + ": " + str(e))
        return None