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
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  created_at TEXT)''')
    
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

def save_alert(pair, percent_change, old_rate, new_rate, email_sent):
    """Save alert to history"""
    conn = get_db()
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
    """Get alert preference for a specific pair"""
    conn = get_db()
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

def get_all_alert_preferences(currency_pairs):
    """Get alert preferences for all pairs"""
    preferences = {}
    for pair in currency_pairs:
        preferences[pair] = get_alert_preference(pair)
    return preferences

def set_alert_preference(pair, enabled, custom_threshold=None, custom_period=None):
    """Set alert preference for a pair"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO alert_preferences 
                 (pair, enabled, custom_threshold, custom_period)
                 VALUES (?, ?, ?, ?)''',
              (pair, 1 if enabled else 0, custom_threshold, custom_period))
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
