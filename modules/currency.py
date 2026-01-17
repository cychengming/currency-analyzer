"""
Currency data module - Fetch and analyze exchange rates
"""

import requests
from datetime import datetime, timedelta
import time

def parse_pair(pair):
    """Split currency pair"""
    return pair.split('/')

def fetch_live_rates(currency_pairs):
    """Fetch current exchange rates"""
    try:
        response = requests.get('https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,JPY,CHF,AUD,CAD,NZD', timeout=10)
        response.raise_for_status()
        today_data = response.json()
        
        # Get yesterday's data for change calculation
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        yesterday_response = requests.get('https://api.frankfurter.app/' + yesterday + '?from=USD&to=EUR,GBP,JPY,CHF,AUD,CAD,NZD', timeout=10)
        
        yesterday_data = None
        if yesterday_response.ok:
            yesterday_data = yesterday_response.json()
        
        def calculate_change(today_rate, yesterday_rate):
            if not yesterday_rate:
                return {'change': 0, 'changePercent': 0}
            change = today_rate - yesterday_rate
            change_percent = (change / yesterday_rate) * 100
            return {'change': change, 'changePercent': change_percent}
        
        # Calculate rates and changes
        rates = {}
        for pair in currency_pairs:
            base, quote = parse_pair(pair)
            
            if base == 'USD':
                today_rate = today_data['rates'][quote]
                yesterday_rate = yesterday_data['rates'][quote] if yesterday_data else today_rate
            else:
                today_rate = 1 / today_data['rates'][base]
                yesterday_rate = 1 / yesterday_data['rates'][base] if yesterday_data else today_rate
            
            change_data = calculate_change(today_rate, yesterday_rate)
            rates[pair] = {
                'rate': round(today_rate, 4),
                'change': round(change_data['change'], 4),
                'changePercent': round(change_data['changePercent'], 2)
            }
        
        return rates
    except Exception as e:
        print("Error fetching live rates: " + str(e))
        return {}

def fetch_historical_data(pair, days):
    """Fetch historical data for a currency pair"""
    try:
        base, quote = parse_pair(pair)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        url = 'https://api.frankfurter.app/' + start_str + '..' + end_str + '?from=' + base + '&to=' + quote
        time.sleep(0.1)  # Rate limiting
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        chart_data = []
        for date_str, rates in sorted(data.get('rates', {}).items()):
            chart_data.append({
                'date': date_str,
                'rate': rates[quote]
            })
        
        return chart_data
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
        
        is_triggered = False
        if trigger_type == 'crosses_above' and price_high:
            is_triggered = previous_rate < price_high and current_rate >= price_high
        elif trigger_type == 'crosses_below' and price_low:
            is_triggered = previous_rate > price_low and current_rate <= price_low
        elif trigger_type == 'between' and price_high and price_low:
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