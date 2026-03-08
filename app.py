#!/usr/bin/env python3
"""
Currency Market Analyzer - Full Stack Backend
Combines web dashboard + monitoring + email alerts
Can be deployed locally or remotely

Modular architecture with separated concerns:
- app.py: Main Flask application and startup
- modules/database.py: SQLite operations
- modules/auth.py: User authentication and password hashing
- modules/currency.py: Exchange rate fetching and trend detection
- modules/email_alert.py: Email notification sending
- modules/monitoring.py: Background monitoring thread
- modules/routes.py: All API endpoints
"""

from flask import Flask
from flask_cors import CORS
import os
import secrets
from datetime import datetime


def _get_persistent_secret_key() -> str:
    """Return a stable SECRET_KEY.

    Priority:
      1) SECRET_KEY env var (recommended)
      2) A key persisted in the mounted /app/data volume

    This prevents session cookies from being invalidated on container restarts.
    """

    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key

    data_dir = os.environ.get('DATA_DIR', '/app/data')
    key_path = os.path.join(data_dir, '.flask_secret_key')

    try:
        if os.path.exists(key_path):
            with open(key_path, 'r', encoding='utf-8') as f:
                k = f.read().strip()
                if k:
                    return k
    except Exception:
        # Fall back to generating a new key below
        pass

    k = secrets.token_hex(32)
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(key_path, 'w', encoding='utf-8') as f:
            f.write(k)
        try:
            os.chmod(key_path, 0o600)
        except Exception:
            pass
    except Exception:
        # If we can't persist, at least run with a generated key
        pass
    return k

# Import modular components
from modules import init_db, create_routes, start_monitoring

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app, supports_credentials=True)
app.secret_key = _get_persistent_secret_key()
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 7  # 7 days

# Currency pairs to monitor
# FX pairs are fetched via frankfurter.app; commodities are fetched via Yahoo Finance.
CURRENCY_PAIRS = [
    'EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD', 'NZD/USD',
    'GOLD/USD', 'SILVER/USD', 'COPPER/USD', 'WHEAT/USD', 'SOYBEAN/USD', 'CORN/USD',
    'WTI/USD', 'BRENT/USD', 'NDX/USD'
]

# ========== REGISTER ALL ROUTES ==========
create_routes(app, CURRENCY_PAIRS)

# ========== STARTUP ==========
if __name__ == '__main__':
    print("\n" + "="*60)
    print("[*] Currency Market Analyzer - Full Stack (Modular)")
    print("="*60)
    
    # Initialize database
    init_db()
    print("[OK] Database initialized")
    
    # Start monitoring thread
    start_monitoring(CURRENCY_PAIRS)
    print("[OK] Monitoring thread started")
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')  # 0.0.0.0 allows remote access
    
    print("\n[*] Server starting on http://" + host + ":" + str(port))
    print("[*] Open your browser to: http://localhost:" + str(port))
    if host == '0.0.0.0':
        print("[*] Remote access: http://YOUR_IP_ADDRESS:" + str(port))
    print("\n[*] Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    app.run(host=host, port=port, debug=False, threaded=True)
