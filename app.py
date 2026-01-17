#!/usr/bin/env python3
"""
Currency Market Analyzer - Full Stack Backend
Combines web dashboard + monitoring + email alerts
Can be deployed locally or remotely
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import threading
import time
import sqlite3
import json
import os

app = Flask(__name__, static_folder='static')
CORS(app)

# ========== CONFIGURATION ==========
GMAIL_USER = os.environ.get('GMAIL_USER', 'your.email@gmail.com')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_PASSWORD', 'xxxx xxxx xxxx xxxx')
DATABASE = 'currency_monitor.db'

# Currency pairs to monitor
CURRENCY_PAIRS = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD', 'NZD/USD']

# Monitoring thread
monitoring_thread = None
monitoring_active = False

# ========== DATABASE SETUP ==========
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Alert history table
    c.execute('''CREATE TABLE IF NOT EXISTS alerts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  pair TEXT,
                  percent_change REAL,
                  old_rate REAL,
                  new_rate REAL,
                  timestamp TEXT,
                  email_sent INTEGER)''')
    
    # Monitoring state table
    c.execute('''CREATE TABLE IF NOT EXISTS monitoring_state
                 (pair TEXT PRIMARY KEY, last_alert_time REAL)''')
    
    # Alert preferences table (per-pair settings)
    c.execute('''CREATE TABLE IF NOT EXISTS alert_preferences
                 (pair TEXT PRIMARY KEY,
                  enabled INTEGER,
                  custom_threshold REAL,
                  custom_period INTEGER)''')
    
    # Default settings if not exists
    default_settings = {
        'trend_threshold': '2.0',
        'detection_period': '30',
        'check_interval': '900',
        'enable_alerts': 'true',
        'enable_sound': 'true',
        'alert_email': '',
        'monitoring_enabled': 'false'
    }
    
    for key, value in default_settings.items():
        c.execute('INSERT OR IGNORE INTO settings VALUES (?, ?)', (key, value))
    
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    """Get setting from database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting(key, value):
    """Save setting to database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

def save_alert(pair, percent_change, old_rate, new_rate, email_sent):
    """Save alert to history"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''INSERT INTO alerts 
                 (pair, percent_change, old_rate, new_rate, timestamp, email_sent)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (pair, percent_change, old_rate, new_rate, 
               datetime.now().isoformat(), 1 if email_sent else 0))
    conn.commit()
    conn.close()

def get_alert_history(limit=50):
    """Get recent alerts"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''SELECT pair, percent_change, old_rate, new_rate, timestamp, email_sent 
                 FROM alerts ORDER BY id DESC LIMIT ?''', (limit,))
    alerts = []
    for row in c.fetchall():
        alerts.append({
            'pair': row[0],
            'percent_change': row[1],
            'old_rate': row[2],
            'new_rate': row[3],
            'timestamp': row[4],
            'email_sent': bool(row[5])
        })
    conn.close()
    return alerts

def get_alert_preference(pair):
    """Get alert preference for a specific pair"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT enabled, custom_threshold, custom_period FROM alert_preferences WHERE pair = ?', (pair,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            'enabled': bool(result[0]),
            'custom_threshold': result[1],
            'custom_period': result[2]
        }
    else:
        # Return defaults if not set
        return {
            'enabled': True,
            'custom_threshold': None,
            'custom_period': None
        }

def get_all_alert_preferences():
    """Get alert preferences for all pairs"""
    preferences = {}
    for pair in CURRENCY_PAIRS:
        preferences[pair] = get_alert_preference(pair)
    return preferences

def set_alert_preference(pair, enabled, custom_threshold=None, custom_period=None):
    """Set alert preference for a pair"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO alert_preferences 
                 (pair, enabled, custom_threshold, custom_period)
                 VALUES (?, ?, ?, ?)''',
              (pair, 1 if enabled else 0, custom_threshold, custom_period))
    conn.commit()
    conn.close()

def delete_alert_from_history(alert_id):
    """Delete a specific alert from history"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM alerts WHERE id = ?', (alert_id,))
    conn.commit()
    conn.close()

def clear_alert_history():
    """Clear all alerts from history"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM alerts')
    conn.commit()
    conn.close()

# ========== CURRENCY DATA FUNCTIONS ==========
def parse_pair(pair):
    """Split currency pair"""
    return pair.split('/')

def fetch_live_rates():
    """Fetch current exchange rates"""
    try:
        response = requests.get('https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,JPY,CHF,AUD,CAD,NZD', timeout=10)
        response.raise_for_status()
        today_data = response.json()
        
        # Get yesterday's data for change calculation
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        yesterday_response = requests.get(f'https://api.frankfurter.app/{yesterday}?from=USD&to=EUR,GBP,JPY,CHF,AUD,CAD,NZD', timeout=10)
        
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
        for pair in CURRENCY_PAIRS:
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
        print(f"Error fetching live rates: {e}")
        return {}

def fetch_historical_data(pair, days):
    """Fetch historical data for a currency pair"""
    try:
        base, quote = parse_pair(pair)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        url = f"https://api.frankfurter.app/{start_str}..{end_str}?from={base}&to={quote}"
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
        print(f"Error fetching historical data for {pair}: {e}")
        return []

def detect_trend(pair):
    """Detect if currency pair shows uptrend"""
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
        print(f"Error detecting trend for {pair}: {e}")
        return None

# ========== EMAIL FUNCTIONS ==========
def send_email_alert(pair, trend_info):
    """Send email alert"""
    try:
        alert_email = get_setting('alert_email', '')
        if not alert_email:
            return False
        
        subject = f"🚨 Currency Alert: {pair} Uptrend Detected!"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="color: #2563eb;">📈 Currency Uptrend Alert</h1>
            <div style="background-color: #f0fdf4; padding: 15px; border-left: 4px solid #10b981;">
                <h2 style="color: #10b981;">{pair}</h2>
                <p style="font-size: 24px;"><strong>Change:</strong> <span style="color: #10b981;">+{trend_info['percent_change']}%</span></p>
            </div>
            <div style="margin-top: 20px;">
                <p><strong>Start Rate ({trend_info['start_date']}):</strong> {trend_info['old_rate']}</p>
                <p><strong>Current Rate ({trend_info['end_date']}):</strong> {trend_info['new_rate']}</p>
                <p><strong>Period:</strong> {get_setting('detection_period', 30)} days</p>
            </div>
            <p style="color: #6b7280; margin-top: 20px; font-size: 12px;">
                Alert sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </body>
        </html>
        """
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = alert_email
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ Email sent for {pair}")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False

# ========== MONITORING LOOP ==========
def monitoring_loop():
    """Background monitoring thread"""
    global monitoring_active
    
    print("🚀 Monitoring thread started")
    
    while monitoring_active:
        try:
            if get_setting('monitoring_enabled', 'false') == 'true':
                print(f"\n{'='*60}")
                print(f"🔍 Checking trends at {datetime.now().strftime('%H:%M:%S')}")
                
                for pair in CURRENCY_PAIRS:
                    trend_info = detect_trend(pair)
                    
                    if trend_info and trend_info['is_trending']:
                        print(f"🔥 {pair}: +{trend_info['percent_change']}%")
                        
                        # Check cooldown
                        conn = sqlite3.connect(DATABASE)
                        c = conn.cursor()
                        c.execute('SELECT last_alert_time FROM monitoring_state WHERE pair = ?', (pair,))
                        result = c.fetchone()
                        
                        should_alert = True
                        if result:
                            last_alert = result[0]
                            if time.time() - last_alert < 3600:  # 1 hour cooldown
                                should_alert = False
                        
                        if should_alert:
                            email_sent = send_email_alert(pair, trend_info)
                            save_alert(pair, trend_info['percent_change'], 
                                     trend_info['old_rate'], trend_info['new_rate'], email_sent)
                            
                            # Update last alert time
                            c.execute('INSERT OR REPLACE INTO monitoring_state VALUES (?, ?)', 
                                    (pair, time.time()))
                            conn.commit()
                        
                        conn.close()
            
            # Sleep for check interval
            interval = int(get_setting('check_interval', 900))
            time.sleep(interval)
            
        except Exception as e:
            print(f"❌ Error in monitoring loop: {e}")
            time.sleep(60)

# ========== API ENDPOINTS ==========

@app.route('/')
def index():
    """Serve main page"""
    return send_from_directory('static', 'index.html')

@app.route('/api/live-rates', methods=['GET'])
def api_live_rates():
    """Get current exchange rates"""
    rates = fetch_live_rates()
    return jsonify(rates)

@app.route('/api/historical/<pair>/<int:days>', methods=['GET'])
def api_historical(pair, days):
    """Get historical data for a pair"""
    data = fetch_historical_data(pair, days)
    return jsonify(data)

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update settings"""
    if request.method == 'POST':
        settings = request.json
        for key, value in settings.items():
            set_setting(key, value)
        return jsonify({'success': True})
    else:
        settings = {
            'trend_threshold': float(get_setting('trend_threshold', 2.0)),
            'detection_period': int(get_setting('detection_period', 30)),
            'check_interval': int(get_setting('check_interval', 900)),
            'enable_alerts': get_setting('enable_alerts', 'true') == 'true',
            'enable_sound': get_setting('enable_sound', 'true') == 'true',
            'alert_email': get_setting('alert_email', ''),
            'monitoring_enabled': get_setting('monitoring_enabled', 'false') == 'true'
        }
        return jsonify(settings)

@app.route('/api/alerts', methods=['GET'])
def api_alerts():
    """Get alert history"""
    alerts = get_alert_history()
    return jsonify(alerts)

@app.route('/api/alerts/preferences', methods=['GET', 'POST'])
def api_alert_preferences():
    """Get or update alert preferences for all pairs"""
    if request.method == 'POST':
        data = request.json
        pair = data.get('pair')
        enabled = data.get('enabled', True)
        custom_threshold = data.get('custom_threshold')
        custom_period = data.get('custom_period')
        
        set_alert_preference(pair, enabled, custom_threshold, custom_period)
        return jsonify({'success': True, 'message': f'Preferences updated for {pair}'})
    else:
        preferences = get_all_alert_preferences()
        return jsonify(preferences)

@app.route('/api/alerts/preferences/<pair>', methods=['GET'])
def api_get_pair_preference(pair):
    """Get alert preference for a specific pair"""
    pref = get_alert_preference(pair)
    pref['pair'] = pair
    return jsonify(pref)

@app.route('/api/alerts/clear', methods=['DELETE'])
def api_clear_alerts():
    """Clear all alerts from history"""
    clear_alert_history()
    return jsonify({'success': True, 'message': 'Alert history cleared'})

@app.route('/api/monitoring/start', methods=['POST'])
def api_start_monitoring():
    """Start monitoring"""
    set_setting('monitoring_enabled', 'true')
    return jsonify({'success': True, 'message': 'Monitoring started'})

@app.route('/api/monitoring/stop', methods=['POST'])
def api_stop_monitoring():
    """Stop monitoring"""
    set_setting('monitoring_enabled', 'false')
    return jsonify({'success': True, 'message': 'Monitoring stopped'})

@app.route('/api/monitoring/status', methods=['GET'])
def api_monitoring_status():
    """Get monitoring status"""
    return jsonify({
        'active': get_setting('monitoring_enabled', 'false') == 'true',
        'thread_running': monitoring_active
    })

@app.route('/api/test-email', methods=['POST'])
def api_test_email():
    """Send test email"""
    try:
        alert_email = get_setting('alert_email', '')
        if not alert_email:
            return jsonify({'success': False, 'error': 'No email configured'})
        
        test_trend = {
            'percent_change': 2.5,
            'old_rate': 1.08,
            'new_rate': 1.11,
            'start_date': '2026-01-01',
            'end_date': '2026-01-17'
        }
        
        success = send_email_alert('EUR/USD (TEST)', test_trend)
        
        if success:
            return jsonify({'success': True, 'message': f'Test email sent to {alert_email}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to send email'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== STARTUP ==========
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Currency Market Analyzer - Full Stack")
    print("="*60)
    
    # Initialize database
    init_db()
    print("✅ Database initialized")
    
    # Start monitoring thread
    monitoring_active = True
    monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
    monitoring_thread.start()
    print("✅ Monitoring thread started")
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')  # 0.0.0.0 allows remote access
    
    print(f"\n🌐 Server starting on http://{host}:{port}")
    print(f"📊 Open your browser to: http://localhost:{port}")
    if host == '0.0.0.0':
        print(f"🌍 Remote access: http://YOUR_IP_ADDRESS:{port}")
    print("\n💡 Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    app.run(host=host, port=port, debug=False, threaded=True)
