"""
Monitoring module - Background monitoring thread and trend detection
"""

import threading
import time
from datetime import datetime

monitoring_active = False
monitoring_thread = None

def monitoring_loop(currency_pairs):
    """Background monitoring thread with multi-condition alert support"""
    global monitoring_active
    from modules.database import get_setting, get_alert_preference, save_alert, get_monitoring_state, set_monitoring_state
    from modules.currency import (detect_trend, detect_historical_high, detect_historical_low,
                                  detect_price_level_cross, detect_volatility_spike, detect_moving_average_crossover)
    from modules.email_alert import send_email_alert
    
    print('[*] Monitoring thread started')
    
    while monitoring_active:
        try:
            if get_setting('monitoring_enabled', 'false') == 'true':
                print('\n' + '='*60)
                print('[*] Checking alerts at ' + datetime.now().strftime('%H:%M:%S'))
                
                for pair in currency_pairs:
                    pref = get_alert_preference(pair)
                    
                    if not pref['enabled']:
                        continue
                    
                    # Check cooldown
                    last_alert = get_monitoring_state(pair)
                    should_alert = True
                    if last_alert and time.time() - last_alert < 3600:  # 1 hour cooldown
                        should_alert = False
                    
                    if not should_alert:
                        continue
                    
                    # Route to appropriate detection function based on alert type
                    alert_info = None
                    alert_type = pref.get('alert_type', 'percentage_change')
                    
                    if alert_type == 'percentage_change':
                        alert_info = detect_trend(pair, currency_pairs)
                        if alert_info and alert_info.get('is_trending'):
                            print('[TREND] ' + pair + ': +' + str(alert_info['percent_change']) + '%')
                    
                    elif alert_type == 'historical_high':
                        alert_info = detect_historical_high(pair, currency_pairs, pref.get('lookback_years', 5))
                        if alert_info and alert_info.get('is_high'):
                            print('[HIGH] ' + pair + ': New ' + str(pref.get('lookback_years', 5)) + '-year high!')
                    
                    elif alert_type == 'historical_low':
                        alert_info = detect_historical_low(pair, currency_pairs, pref.get('lookback_years', 5))
                        if alert_info and alert_info.get('is_low'):
                            print('[LOW] ' + pair + ': New ' + str(pref.get('lookback_years', 5)) + '-year low!')
                    
                    elif alert_type == 'price_level':
                        alert_info = detect_price_level_cross(pair, currency_pairs,
                                                             pref.get('price_high'),
                                                             pref.get('price_low'),
                                                             pref.get('trigger_type', 'crosses_above'))
                        if alert_info and alert_info.get('is_triggered'):
                            print('[PRICE] ' + pair + ': Price level triggered!')
                    
                    elif alert_type == 'volatility':
                        alert_info = detect_volatility_spike(pair, currency_pairs, volatility_type=pref.get('volatility_type', 'high'))
                        if alert_info and alert_info.get('is_spike'):
                            print('[VOL] ' + pair + ': Volatility spike detected!')
                    
                    elif alert_type == 'moving_average':
                        alert_info = detect_moving_average_crossover(pair, currency_pairs,
                                                                    pref.get('ma_short_period', 10),
                                                                    pref.get('ma_long_period', 50),
                                                                    pref.get('signal_type', 'golden_cross'))
                        if alert_info and alert_info.get('is_crossover'):
                            print('[MA] ' + pair + ': Moving average ' + pref.get('signal_type', 'crossover') + '!')
                    
                    # If alert triggered, send notification
                    if alert_info and any([
                        alert_info.get('is_trending'),
                        alert_info.get('is_high'),
                        alert_info.get('is_low'),
                        alert_info.get('is_triggered'),
                        alert_info.get('is_spike'),
                        alert_info.get('is_crossover')
                    ]):
                        email_sent = send_email_alert(pair, alert_info, alert_type=alert_type)
                        save_alert(pair, alert_info.get('percent_change', 0),
                                 alert_info.get('old_rate', 0), alert_info.get('new_rate', alert_info.get('current_rate', 0)),
                                 email_sent, alert_type=alert_type)
                        set_monitoring_state(pair, time.time())
            
            # Sleep for check interval
            interval = int(get_setting('check_interval', 900))
            time.sleep(interval)
            
        except Exception as e:
            print('[ERROR] Error in monitoring loop: ' + str(e))
            time.sleep(60)

def start_monitoring(currency_pairs):
    """Start monitoring thread"""
    global monitoring_active, monitoring_thread
    
    if not monitoring_active:
        monitoring_active = True
        monitoring_thread = threading.Thread(target=monitoring_loop, args=(currency_pairs,), daemon=True)
        monitoring_thread.start()
        print('[OK] Monitoring thread started')

def stop_monitoring():
    """Stop monitoring thread"""
    global monitoring_active
    monitoring_active = False
    print('[STOP] Monitoring thread stopped')

def is_monitoring_active():
    """Check if monitoring is active"""
    return monitoring_active
