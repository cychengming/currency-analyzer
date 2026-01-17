"""
Monitoring module - Background monitoring thread and trend detection
"""

import threading
import time
from datetime import datetime

monitoring_active = False
monitoring_thread = None

def monitoring_loop(currency_pairs):
    """Background monitoring thread"""
    global monitoring_active
    from modules.database import get_setting, save_alert, get_monitoring_state, set_monitoring_state
    from modules.currency import detect_trend
    from modules.email_alert import send_email_alert
    
    print('[*] Monitoring thread started')
    
    while monitoring_active:
        try:
            if get_setting('monitoring_enabled', 'false') == 'true':
                print('\n' + '='*60)
                print('[*] Checking trends at ' + datetime.now().strftime('%H:%M:%S'))
                
                for pair in currency_pairs:
                    trend_info = detect_trend(pair, currency_pairs)
                    
                    if trend_info and trend_info['is_trending']:
                        print('[TREND] ' + pair + ': +' + str(trend_info['percent_change']) + '%')
                        
                        # Check cooldown
                        last_alert = get_monitoring_state(pair)
                        
                        should_alert = True
                        if last_alert:
                            if time.time() - last_alert < 3600:  # 1 hour cooldown
                                should_alert = False
                        
                        if should_alert:
                            email_sent = send_email_alert(pair, trend_info)
                            save_alert(pair, trend_info['percent_change'], 
                                     trend_info['old_rate'], trend_info['new_rate'], email_sent)
                            
                            # Update last alert time
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
