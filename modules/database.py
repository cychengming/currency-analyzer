"""
Database module - Handle all SQLite operations
"""

import sqlite3
import os
from datetime import datetime

# Database configuration
DATA_DIR = '/app/data'
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE = os.path.join(DATA_DIR, 'currency_monitor.db')

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize SQLite database"""
    conn = get_db()
    c = conn.cursor()
    
    # Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Alert history table (enhanced with alert type and trigger values)
    c.execute('''CREATE TABLE IF NOT EXISTS alerts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  pair TEXT,
                  percent_change REAL,
                  old_rate REAL,
                  new_rate REAL,
                  timestamp TEXT,
                  email_sent INTEGER,
                  alert_type TEXT,
                  trigger_value REAL,
                  threshold_value REAL)''')
    
    # Monitoring state table
    c.execute('''CREATE TABLE IF NOT EXISTS monitoring_state
                 (pair TEXT PRIMARY KEY, last_alert_time REAL)''')
    
    # Alert preferences table (enhanced with multiple condition types)
    c.execute('''CREATE TABLE IF NOT EXISTS alert_preferences
                 (pair TEXT PRIMARY KEY,
                  enabled INTEGER,
                  alert_type TEXT DEFAULT 'percentage_change',
                  
                  custom_threshold REAL,
                  custom_period INTEGER,
                  enable_trend_consistency INTEGER DEFAULT 1,
                  
                  lookback_years INTEGER DEFAULT 5,
                  
                  price_high REAL,
                  price_low REAL,
                  trigger_type TEXT,
                  
                  volatility_type TEXT,
                  
                  ma_short_period INTEGER DEFAULT 10,
                  ma_long_period INTEGER DEFAULT 50,
                  signal_type TEXT)''')
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  created_at TEXT)''')

    # Apply schema migrations for existing databases
    _apply_schema_migrations(c)
    
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

def _apply_schema_migrations(cursor):
    """Apply in-place schema migrations for existing databases."""
    try:
        cursor.execute("PRAGMA table_info(alert_preferences)")
        pref_columns = {row[1] for row in cursor.fetchall()}

        pref_additions = {
            'alert_type': "ALTER TABLE alert_preferences ADD COLUMN alert_type TEXT DEFAULT 'percentage_change'",
            'enable_trend_consistency': "ALTER TABLE alert_preferences ADD COLUMN enable_trend_consistency INTEGER DEFAULT 1",
            'lookback_years': "ALTER TABLE alert_preferences ADD COLUMN lookback_years INTEGER DEFAULT 5",
            'price_high': "ALTER TABLE alert_preferences ADD COLUMN price_high REAL",
            'price_low': "ALTER TABLE alert_preferences ADD COLUMN price_low REAL",
            'trigger_type': "ALTER TABLE alert_preferences ADD COLUMN trigger_type TEXT",
            'volatility_type': "ALTER TABLE alert_preferences ADD COLUMN volatility_type TEXT",
            'ma_short_period': "ALTER TABLE alert_preferences ADD COLUMN ma_short_period INTEGER DEFAULT 10",
            'ma_long_period': "ALTER TABLE alert_preferences ADD COLUMN ma_long_period INTEGER DEFAULT 50",
            'signal_type': "ALTER TABLE alert_preferences ADD COLUMN signal_type TEXT"
        }

        for col, ddl in pref_additions.items():
            if col not in pref_columns:
                cursor.execute(ddl)

        cursor.execute("PRAGMA table_info(alerts)")
        alert_columns = {row[1] for row in cursor.fetchall()}

        alert_additions = {
            'alert_type': "ALTER TABLE alerts ADD COLUMN alert_type TEXT",
            'trigger_value': "ALTER TABLE alerts ADD COLUMN trigger_value REAL",
            'threshold_value': "ALTER TABLE alerts ADD COLUMN threshold_value REAL"
        }

        for col, ddl in alert_additions.items():
            if col not in alert_columns:
                cursor.execute(ddl)
    except Exception as e:
        print("[WARN] Schema migration issue: " + str(e))

def get_setting(key, default=None):
    """Get setting from database"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting(key, value):
    """Save setting to database"""
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

def save_alert(pair, percent_change, old_rate, new_rate, email_sent, alert_type='percentage_change', trigger_value=None, threshold_value=None):
    """Save alert to history with type information"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO alerts 
                 (pair, percent_change, old_rate, new_rate, timestamp, email_sent, alert_type, trigger_value, threshold_value)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (pair, percent_change, old_rate, new_rate, 
               datetime.now().isoformat(), 1 if email_sent else 0, alert_type, trigger_value, threshold_value))
    conn.commit()
    conn.close()
def get_alert_history(limit=50):
    """Get recent alerts"""
    conn = get_db()
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

def clear_alert_history():
    """Clear all alerts from history"""
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM alerts')
    conn.commit()
    conn.close()


def get_alert_preference(pair):
    """Get alert preference for a specific pair (supports all alert types)"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT enabled, alert_type, custom_threshold, custom_period, enable_trend_consistency,
                        lookback_years, price_high, price_low, trigger_type, volatility_type,
                        ma_short_period, ma_long_period, signal_type
                 FROM alert_preferences WHERE pair = ?''', (pair,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            'enabled': bool(result[0]),
            'alert_type': result[1] or 'percentage_change',
            'custom_threshold': result[2],
            'custom_period': result[3],
            'enable_trend_consistency': bool(result[4]),
            'lookback_years': result[5] or 5,
            'price_high': result[6],
            'price_low': result[7],
            'trigger_type': result[8],
            'volatility_type': result[9],
            'ma_short_period': result[10] or 10,
            'ma_long_period': result[11] or 50,
            'signal_type': result[12]
        }
    else:
        # Return defaults if not set
        return {
            'enabled': True,
            'alert_type': 'percentage_change',
            'custom_threshold': None,
            'custom_period': None,
            'enable_trend_consistency': True,
            'lookback_years': 5,
            'price_high': None,
            'price_low': None,
            'trigger_type': None,
            'volatility_type': None,
            'ma_short_period': 10,
            'ma_long_period': 50,
            'signal_type': None
        }

def get_all_alert_preferences(currency_pairs):
    """Get alert preferences for all pairs"""
    preferences = {}
    for pair in currency_pairs:
        preferences[pair] = get_alert_preference(pair)
    return preferences

def set_alert_preference(pair, enabled, custom_threshold=None, custom_period=None, alert_type='percentage_change', **kwargs):
    """Set alert preference for a pair with support for multiple alert types"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO alert_preferences 
                 (pair, enabled, alert_type, custom_threshold, custom_period,
                  enable_trend_consistency, lookback_years, price_high, price_low,
                  trigger_type, volatility_type, ma_short_period, ma_long_period, signal_type)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (pair, 1 if enabled else 0, alert_type, custom_threshold, custom_period,
               kwargs.get('enable_trend_consistency', 1),
               kwargs.get('lookback_years', 5),
               kwargs.get('price_high'),
               kwargs.get('price_low'),
               kwargs.get('trigger_type'),
               kwargs.get('volatility_type'),
               kwargs.get('ma_short_period', 10),
               kwargs.get('ma_long_period', 50),
               kwargs.get('signal_type')))
    conn.commit()
    conn.close()

def get_monitoring_state(pair):
    """Get last alert time for a pair"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT last_alert_time FROM monitoring_state WHERE pair = ?', (pair,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def set_monitoring_state(pair, last_alert_time):
    """Set last alert time for a pair"""
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO monitoring_state VALUES (?, ?)', (pair, last_alert_time))
    conn.commit()
    conn.close()
