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

# Import modular components
from modules import init_db, create_routes, start_monitoring

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app, supports_credentials=True)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 7  # 7 days

# Currency pairs to monitor
CURRENCY_PAIRS = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD', 'NZD/USD']

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
