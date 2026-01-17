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
