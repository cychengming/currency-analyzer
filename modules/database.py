"""
Database module - Handle all SQLite operations
"""

import sqlite3
import os
from datetime import datetime, timedelta

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

    # Trade diary / risk journal
    c.execute('''CREATE TABLE IF NOT EXISTS trade_journal
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL,
                  pair TEXT NOT NULL,
                  side TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'open',
                  entry_price REAL,
                  stop_price REAL,
                  close_price REAL,
                  quantity REAL,
                  risk_amount_usd REAL,
                  risk_pct_of_equity REAL,
                  atr REAL,
                  sigma REAL,
                  entry_reason TEXT,
                  close_reason TEXT,
                  notes TEXT,
                  opened_at TEXT,
                  closed_at TEXT,
                  created_at TEXT,
                  updated_at TEXT)''')

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
        'monitoring_enabled': 'false',
        'daily_risk_limit_pct': '3.0'
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

        cursor.execute("PRAGMA table_info(trade_journal)")
        trade_columns = {row[1] for row in cursor.fetchall()}

        trade_additions = {
            'status': "ALTER TABLE trade_journal ADD COLUMN status TEXT NOT NULL DEFAULT 'open'",
            'close_price': "ALTER TABLE trade_journal ADD COLUMN close_price REAL",
            'quantity': "ALTER TABLE trade_journal ADD COLUMN quantity REAL",
            'risk_amount_usd': "ALTER TABLE trade_journal ADD COLUMN risk_amount_usd REAL",
            'risk_pct_of_equity': "ALTER TABLE trade_journal ADD COLUMN risk_pct_of_equity REAL",
            'atr': "ALTER TABLE trade_journal ADD COLUMN atr REAL",
            'sigma': "ALTER TABLE trade_journal ADD COLUMN sigma REAL",
            'entry_reason': "ALTER TABLE trade_journal ADD COLUMN entry_reason TEXT",
            'close_reason': "ALTER TABLE trade_journal ADD COLUMN close_reason TEXT",
            'notes': "ALTER TABLE trade_journal ADD COLUMN notes TEXT",
            'opened_at': "ALTER TABLE trade_journal ADD COLUMN opened_at TEXT",
            'closed_at': "ALTER TABLE trade_journal ADD COLUMN closed_at TEXT",
            'created_at': "ALTER TABLE trade_journal ADD COLUMN created_at TEXT",
            'updated_at': "ALTER TABLE trade_journal ADD COLUMN updated_at TEXT"
        }

        for col, ddl in trade_additions.items():
            if trade_columns and col not in trade_columns:
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


def clear_monitoring_state():
    """Clear monitoring cooldown state for all pairs"""
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM monitoring_state')
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


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _today_window():
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _trade_row_to_dict(row):
    if not row:
        return None

    item = dict(row)
    entry_price = item.get('entry_price')
    close_price = item.get('close_price')
    quantity = item.get('quantity')
    side = str(item.get('side') or 'long').lower()
    realized_pnl = None

    if entry_price is not None and close_price is not None and quantity is not None:
        try:
            entry_price = float(entry_price)
            close_price = float(close_price)
            quantity = float(quantity)
            if side == 'short':
                realized_pnl = (entry_price - close_price) * quantity
            else:
                realized_pnl = (close_price - entry_price) * quantity
        except (TypeError, ValueError):
            realized_pnl = None

    item['realized_pnl'] = round(realized_pnl, 4) if realized_pnl is not None else None
    return item


def create_trade_journal_entry(username, pair, side, entry_price, stop_price, quantity, risk_amount_usd,
                               risk_pct_of_equity=None, atr=None, sigma=None, entry_reason='', notes=''):
    """Create a new open trade journal entry."""
    now = _now_iso()
    conn = get_db()
    c = conn.cursor()
    c.execute(
        '''INSERT INTO trade_journal
           (username, pair, side, status, entry_price, stop_price, quantity,
            risk_amount_usd, risk_pct_of_equity, atr, sigma,
            entry_reason, close_reason, notes, opened_at, closed_at, created_at, updated_at)
           VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, ?, ?)''',
        (
            username,
            pair,
            side,
            entry_price,
            stop_price,
            quantity,
            risk_amount_usd,
            risk_pct_of_equity,
            atr,
            sigma,
            entry_reason,
            notes,
            now,
            now,
            now,
        )
    )
    trade_id = c.lastrowid
    conn.commit()
    c.execute('SELECT * FROM trade_journal WHERE id = ? AND username = ?', (trade_id, username))
    row = c.fetchone()
    conn.close()
    return _trade_row_to_dict(row)


def get_trade_journal_entry(trade_id, username):
    """Get a single trade journal entry for a user."""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM trade_journal WHERE id = ? AND username = ?', (trade_id, username))
    row = c.fetchone()
    conn.close()
    return _trade_row_to_dict(row)


def close_trade_journal_entry(trade_id, username, close_price=None, close_reason=''):
    """Close an existing open trade journal entry."""
    now = _now_iso()
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM trade_journal WHERE id = ? AND username = ?', (trade_id, username))
    current = c.fetchone()
    if not current:
        conn.close()
        return None

    c.execute(
        '''UPDATE trade_journal
           SET status = 'closed', close_price = ?, close_reason = ?, closed_at = ?, updated_at = ?
           WHERE id = ? AND username = ?''',
        (close_price, close_reason, now, now, trade_id, username)
    )
    conn.commit()
    c.execute('SELECT * FROM trade_journal WHERE id = ? AND username = ?', (trade_id, username))
    row = c.fetchone()
    conn.close()
    return _trade_row_to_dict(row)


def update_trade_journal_entry(trade_id, username, pair, side, entry_price, stop_price, quantity,
                               risk_amount_usd, risk_pct_of_equity=None, atr=None, sigma=None,
                               entry_reason='', notes='', status='open', close_price=None,
                               close_reason=None, closed_at=None):
    """Update an existing trade journal entry."""
    now = _now_iso()
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM trade_journal WHERE id = ? AND username = ?', (trade_id, username))
    current = c.fetchone()
    if not current:
        conn.close()
        return None

    if status == 'open':
        close_price = None
        close_reason = None
        closed_at = None
    elif closed_at is None:
        closed_at = current['closed_at'] or now

    c.execute(
        '''UPDATE trade_journal
           SET pair = ?, side = ?, status = ?, entry_price = ?, stop_price = ?, close_price = ?,
               quantity = ?, risk_amount_usd = ?, risk_pct_of_equity = ?, atr = ?, sigma = ?,
               entry_reason = ?, close_reason = ?, notes = ?, closed_at = ?, updated_at = ?
           WHERE id = ? AND username = ?''',
        (
            pair,
            side,
            status,
            entry_price,
            stop_price,
            close_price,
            quantity,
            risk_amount_usd,
            risk_pct_of_equity,
            atr,
            sigma,
            entry_reason,
            close_reason,
            notes,
            closed_at,
            now,
            trade_id,
            username,
        )
    )
    conn.commit()
    c.execute('SELECT * FROM trade_journal WHERE id = ? AND username = ?', (trade_id, username))
    row = c.fetchone()
    conn.close()
    return _trade_row_to_dict(row)


def get_trade_journal_entries(username, limit=50):
    """Get recent trade journal entries for a user."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        '''SELECT * FROM trade_journal
           WHERE username = ?
           ORDER BY opened_at DESC, id DESC
           LIMIT ?''',
        (username, int(limit))
    )
    rows = c.fetchall()
    conn.close()
    return [_trade_row_to_dict(row) for row in rows]


def get_trade_risk_summary(username, equity, daily_limit_pct, planned_risk_usd=0.0):
    """Summarize today's risk usage and current active exposure for a user."""
    try:
        equity = float(equity or 0)
    except (TypeError, ValueError):
        equity = 0.0

    try:
        daily_limit_pct = float(daily_limit_pct or 0)
    except (TypeError, ValueError):
        daily_limit_pct = 0.0

    try:
        planned_risk_usd = float(planned_risk_usd or 0)
    except (TypeError, ValueError):
        planned_risk_usd = 0.0

    today_start, tomorrow_start = _today_window()
    conn = get_db()
    c = conn.cursor()

    c.execute(
        '''SELECT
               COUNT(*) AS trade_count,
               COALESCE(SUM(risk_amount_usd), 0) AS opened_today_risk_usd
           FROM trade_journal
           WHERE username = ?
             AND opened_at >= ?
             AND opened_at < ?''',
        (username, today_start, tomorrow_start)
    )
    opened_row = c.fetchone()

    c.execute(
        '''SELECT
               COUNT(*) AS open_trade_count,
               COALESCE(SUM(risk_amount_usd), 0) AS active_risk_usd
           FROM trade_journal
           WHERE username = ?
             AND status = 'open' ''',
        (username,)
    )
    active_row = c.fetchone()
    conn.close()

    opened_today_risk_usd = float((opened_row['opened_today_risk_usd'] if opened_row else 0) or 0)
    active_risk_usd = float((active_row['active_risk_usd'] if active_row else 0) or 0)
    trade_count = int((opened_row['trade_count'] if opened_row else 0) or 0)
    open_trade_count = int((active_row['open_trade_count'] if active_row else 0) or 0)
    daily_limit_usd = equity * (daily_limit_pct / 100.0) if equity > 0 and daily_limit_pct > 0 else 0.0
    projected_opened_today = opened_today_risk_usd + planned_risk_usd
    remaining_risk_usd = daily_limit_usd - opened_today_risk_usd
    projected_remaining_risk_usd = daily_limit_usd - projected_opened_today
    can_open_new_trade = True if daily_limit_usd <= 0 else projected_opened_today <= (daily_limit_usd + 1e-9)

    return {
        'equity': round(equity, 4),
        'daily_limit_pct': round(daily_limit_pct, 4),
        'daily_limit_usd': round(daily_limit_usd, 4),
        'opened_today_risk_usd': round(opened_today_risk_usd, 4),
        'active_risk_usd': round(active_risk_usd, 4),
        'planned_risk_usd': round(planned_risk_usd, 4),
        'projected_opened_today_risk_usd': round(projected_opened_today, 4),
        'remaining_risk_usd': round(remaining_risk_usd, 4),
        'projected_remaining_risk_usd': round(projected_remaining_risk_usd, 4),
        'today_trade_count': trade_count,
        'open_trade_count': open_trade_count,
        'can_open_new_trade': can_open_new_trade,
    }
