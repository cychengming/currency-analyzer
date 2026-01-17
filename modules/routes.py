"""
API Routes - All Flask endpoints
"""

from flask import Blueprint, jsonify, request, send_from_directory, session
from urllib.parse import unquote
from modules.auth import login_required, register_user, authenticate_user
from modules.database import (
    get_setting, set_setting, get_alert_history, clear_alert_history,
    get_all_alert_preferences, set_alert_preference, get_alert_preference
)
from modules.currency import fetch_live_rates, fetch_historical_data
from modules.email_alert import send_email_alert

def create_routes(app, currency_pairs):
    """Create and register all API routes"""
    
    @app.route('/')
    def index():
        """Serve login page"""
        return send_from_directory('static', 'login.html')

    @app.route('/dashboard.html')
    def dashboard():
        """Serve dashboard page"""
        return send_from_directory('static', 'dashboard.html')

    @app.route('/login.html')
    def login():
        """Serve login page"""
        return send_from_directory('static', 'login.html')

    # ========== AUTHENTICATION ROUTES ==========
    
    @app.route('/api/auth/register', methods=['POST'])
    def api_register():
        """Register new user"""
        try:
            data = request.json
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            
            if not username or not password:
                return jsonify({'success': False, 'error': 'Username and password required'})
            
            if len(username) < 3:
                return jsonify({'success': False, 'error': 'Username must be at least 3 characters'})
            
            if len(password) < 6:
                return jsonify({'success': False, 'error': 'Password must be at least 6 characters'})
            
            if register_user(username, password):
                return jsonify({'success': True, 'message': 'Registration successful'})
            else:
                return jsonify({'success': False, 'error': 'Username already exists'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        """Login user"""
        try:
            data = request.json
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            
            if not username or not password:
                return jsonify({'success': False, 'error': 'Username and password required'})
            
            if authenticate_user(username, password):
                session['username'] = username
                return jsonify({'success': True, 'message': 'Login successful'})
            else:
                return jsonify({'success': False, 'error': 'Invalid username or password'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/auth/logout', methods=['POST'])
    def api_logout():
        """Logout user"""
        session.clear()
        return jsonify({'success': True, 'message': 'Logged out'})

    @app.route('/api/auth/status', methods=['GET'])
    def api_auth_status():
        """Get authentication status"""
        username = session.get('username')
        return jsonify({
            'logged_in': username is not None,
            'username': username
        })

    # ========== CURRENCY ROUTES ==========
    
    @app.route('/api/live-rates', methods=['GET'])
    @login_required
    def api_live_rates():
        """Get current exchange rates"""
        rates = fetch_live_rates(currency_pairs)
        return jsonify(rates)

    @app.route('/api/historical/<path:pair>/<int:days>', methods=['GET'])
    @login_required
    def api_historical(pair, days):
        """Get historical data for a pair"""
        pair = unquote(pair)
        data = fetch_historical_data(pair, days)
        return jsonify(data)

    # ========== SETTINGS ROUTES ==========
    
    @app.route('/api/settings', methods=['GET', 'POST'])
    @login_required
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

    # ========== ALERT ROUTES ==========
    
    @app.route('/api/alerts', methods=['GET'])
    @login_required
    def api_alerts():
        """Get alert history"""
        alerts = get_alert_history()
        return jsonify(alerts)

    @app.route('/api/alerts/preferences', methods=['GET', 'POST'])
    @login_required
    def api_alert_preferences():
        """Get or update alert preferences for all pairs"""
        if request.method == 'POST':
            data = request.json
            pair = data.get('pair')
            enabled = data.get('enabled', True)
            custom_threshold = data.get('custom_threshold')
            custom_period = data.get('custom_period')
            
            set_alert_preference(pair, enabled, custom_threshold, custom_period)
            return jsonify({'success': True, 'message': 'Preferences updated for ' + pair})
        else:
            preferences = get_all_alert_preferences(currency_pairs)
            return jsonify(preferences)

    @app.route('/api/alerts/preferences/<path:pair>', methods=['GET'])
    @login_required
    def api_get_pair_preference(pair):
        """Get alert preference for a specific pair"""
        pref = get_alert_preference(pair)
        pref['pair'] = pair
        return jsonify(pref)

    @app.route('/api/alerts/clear', methods=['DELETE'])
    @login_required
    def api_clear_alerts():
        """Clear all alerts from history"""
        clear_alert_history()
        return jsonify({'success': True, 'message': 'Alert history cleared'})

    # ========== MONITORING ROUTES ==========
    
    @app.route('/api/monitoring/start', methods=['POST'])
    @login_required
    def api_start_monitoring():
        """Start monitoring"""
        set_setting('monitoring_enabled', 'true')
        return jsonify({'success': True, 'message': 'Monitoring started'})

    @app.route('/api/monitoring/stop', methods=['POST'])
    @login_required
    def api_stop_monitoring():
        """Stop monitoring"""
        set_setting('monitoring_enabled', 'false')
        return jsonify({'success': True, 'message': 'Monitoring stopped'})

    @app.route('/api/monitoring/status', methods=['GET'])
    @login_required
    def api_monitoring_status():
        """Get monitoring status"""
        from modules.monitoring import is_monitoring_active
        return jsonify({
            'active': get_setting('monitoring_enabled', 'false') == 'true',
            'thread_running': is_monitoring_active()
        })

    @app.route('/api/test-email', methods=['POST'])
    @login_required
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
                return jsonify({'success': True, 'message': 'Test email sent to ' + alert_email})
            else:
                return jsonify({'success': False, 'error': 'Failed to send email'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
