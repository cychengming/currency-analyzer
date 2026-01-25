"""
API Routes - All Flask endpoints
"""

from flask import Blueprint, jsonify, request, send_from_directory, session
from urllib.parse import unquote
from modules.auth import login_required, register_user, authenticate_user
from modules.database import (
    get_setting, set_setting, get_alert_history, clear_alert_history,
    get_all_alert_preferences, set_alert_preference, get_alert_preference,
    clear_monitoring_state
)
from modules.currency import fetch_live_rates, fetch_historical_data, fetch_historical_ohlc_data
from modules.email_alert import send_email_alert
from modules.backtest import run_backtest

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

    @app.route('/api/historical-ohlc/<path:pair>/<int:days>', methods=['GET'])
    @login_required
    def api_historical_ohlc(pair, days):
        """Get historical OHLC data for a pair."""
        pair = unquote(pair)
        data = fetch_historical_ohlc_data(pair, days)
        return jsonify(data)

    @app.route('/api/backtest', methods=['POST'])
    @login_required
    def api_backtest():
        """Run a simple backtest for a pair given entry/exit rules.

        Expected JSON body:
        {
          "pair": "GOLD/USD",
          "days": 730,
          "entry": { "type": "long_term_uptrend", ... },
          "exit": { "max_holding_days": 60, "stop_loss_pct": 5, "take_profit_pct": 10, "signal": {...} },
          "initial_capital": 10000,
          "allow_multiple_trades": true
        }
        """
        try:
            data = request.json or {}
            pair = data.get('pair')
            if not pair:
                return jsonify({'success': False, 'error': 'pair is required'}), 400

            try:
                days = int(data.get('days', 365))
            except (TypeError, ValueError):
                days = 365

            entry = data.get('entry') or {}
            exit_cfg = data.get('exit') or {}
            initial_capital = data.get('initial_capital', 10000.0)
            try:
                initial_capital = float(initial_capital)
            except (TypeError, ValueError):
                initial_capital = 10000.0

            allow_multiple_trades = data.get('allow_multiple_trades', True)
            allow_multiple_trades = bool(allow_multiple_trades)

            result = run_backtest(
                pair=str(pair),
                days=days,
                entry=entry,
                exit_cfg=exit_cfg,
                initial_capital=initial_capital,
                allow_multiple_trades=allow_multiple_trades,
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

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
        """Get or update alert preferences for all pairs with multi-condition support"""
        if request.method == 'POST':
            data = request.json
            pair = data.get('pair')
            enabled = data.get('enabled', True)
            alert_type = data.get('alert_type', 'percentage_change')
            
            # Extract parameters based on alert type
            custom_threshold = data.get('custom_threshold')
            custom_period = data.get('custom_period')
            enable_trend_consistency = data.get('enable_trend_consistency', True)
            lookback_years = data.get('lookback_years', 5)
            price_high = data.get('price_high')
            price_low = data.get('price_low')
            trigger_type = data.get('trigger_type')
            volatility_type = data.get('volatility_type')
            ma_short_period = data.get('ma_short_period', 10)
            ma_long_period = data.get('ma_long_period', 50)
            signal_type = data.get('signal_type')

            # Map UI parameter names (moving_average / other MA-driven conditions)
            if ma_short_period == 10 and data.get('short_ma_period') is not None:
                ma_short_period = data.get('short_ma_period')
            if ma_long_period == 50 and data.get('long_ma_period') is not None:
                ma_long_period = data.get('long_ma_period')

            # Map UI parameter names (percentage_change)
            if alert_type == 'percentage_change':
                if custom_threshold is None:
                    custom_threshold = data.get('change_threshold')
                if custom_period is None:
                    custom_period = data.get('detection_period')

            # Map UI parameter names (long_term_uptrend)
            if alert_type == 'long_term_uptrend':
                if custom_threshold is None:
                    custom_threshold = data.get('change_threshold')
                if custom_period is None:
                    custom_period = data.get('detection_period')

            # Normalize numeric inputs (handles string values from clients)
            try:
                custom_threshold = float(custom_threshold) if custom_threshold is not None else None
            except (TypeError, ValueError):
                custom_threshold = None
            try:
                custom_period = int(custom_period) if custom_period is not None else None
            except (TypeError, ValueError):
                custom_period = None
            try:
                lookback_years = int(lookback_years) if lookback_years is not None else 5
            except (TypeError, ValueError):
                lookback_years = 5
            try:
                price_high = float(price_high) if price_high is not None else None
            except (TypeError, ValueError):
                price_high = None
            try:
                price_low = float(price_low) if price_low is not None else None
            except (TypeError, ValueError):
                price_low = None

            # Default trigger_type for price level when not provided
            if alert_type == 'price_level' and not trigger_type:
                if price_high is not None and price_low is not None:
                    trigger_type = 'between'
                else:
                    trigger_type = 'crosses_above'
            try:
                ma_short_period = int(ma_short_period) if ma_short_period is not None else 10
            except (TypeError, ValueError):
                ma_short_period = 10
            try:
                ma_long_period = int(ma_long_period) if ma_long_period is not None else 50
            except (TypeError, ValueError):
                ma_long_period = 50
            
            set_alert_preference(
                pair, enabled, custom_threshold, custom_period,
                alert_type=alert_type,
                enable_trend_consistency=enable_trend_consistency,
                lookback_years=lookback_years,
                price_high=price_high,
                price_low=price_low,
                trigger_type=trigger_type,
                volatility_type=volatility_type,
                ma_short_period=ma_short_period,
                ma_long_period=ma_long_period,
                signal_type=signal_type
            )
            return jsonify({'success': True, 'message': 'Preferences updated for ' + pair})
        else:
            preferences = get_all_alert_preferences(currency_pairs)
            return jsonify(preferences)

    @app.route('/api/alerts/conditions', methods=['GET'])
    @login_required
    def api_alert_conditions():
        """Get available alert condition types and their parameters"""
        conditions = {
            'percentage_change': {
                'name': 'Percentage Change (Trend)',
                'description': 'Alert when price changes by a percentage over a period',
                'parameters': {
                    'change_threshold': {'type': 'number', 'min': 0.1, 'max': 20, 'default': 2, 'unit': '%'},
                    'detection_period': {'type': 'number', 'min': 1, 'max': 365, 'default': 30, 'unit': 'days'},
                    'enable_trend_consistency': {'type': 'boolean', 'default': True}
                }
            },
            'long_term_uptrend': {
                'name': 'Long-Term Upside Trend (Combined)',
                'description': 'Combined confirmation: % change + bullish MA + positive regression (high confidence)',
                'parameters': {
                    'change_threshold': {'type': 'number', 'min': 0.1, 'max': 100, 'default': 5, 'unit': '%'},
                    'detection_period': {'type': 'number', 'min': 30, 'max': 3650, 'default': 365, 'unit': 'days'},
                    'enable_trend_consistency': {'type': 'boolean', 'default': True},
                    'short_ma_period': {'type': 'number', 'min': 7, 'max': 200, 'default': 50, 'unit': 'days'},
                    'long_ma_period': {'type': 'number', 'min': 50, 'max': 3650, 'default': 200, 'unit': 'days'}
                }
            },
            'historical_high': {
                'name': 'Historical High',
                'description': 'Alert when price reaches new high within lookback period',
                'parameters': {
                    'lookback_years': {'type': 'select', 'options': [1, 3, 5, 10], 'default': 5}
                }
            },
            'historical_low': {
                'name': 'Historical Low',
                'description': 'Alert when price reaches new low within lookback period',
                'parameters': {
                    'lookback_years': {'type': 'select', 'options': [1, 3, 5, 10], 'default': 5}
                }
            },
            'price_level': {
                'name': 'Price Level Bands',
                'description': 'Alert when price crosses above/below defined levels',
                'parameters': {
                    'price_high': {'type': 'number', 'min': 0, 'default': None, 'unit': 'rate'},
                    'price_low': {'type': 'number', 'min': 0, 'default': None, 'unit': 'rate'},
                    'trigger_type': {'type': 'select', 'options': ['crosses_above', 'crosses_below', 'between'], 'default': 'crosses_above'}
                }
            },
            'volatility': {
                'name': 'Volatility Threshold',
                'description': 'Alert when volatility spikes above or below normal',
                'parameters': {
                    'volatility_type': {'type': 'select', 'options': ['high', 'low'], 'default': 'high'}
                }
            },
            'moving_average': {
                'name': 'Moving Average Crossover',
                'description': 'Alert on golden cross (bullish) or death cross (bearish)',
                'parameters': {
                    'short_ma_period': {'type': 'number', 'min': 7, 'max': 50, 'default': 10, 'unit': 'days'},
                    'long_ma_period': {'type': 'number', 'min': 50, 'max': 365, 'default': 50, 'unit': 'days'},
                    'signal_type': {'type': 'select', 'options': ['golden_cross', 'death_cross'], 'default': 'golden_cross'}
                }
            }
        }
        return jsonify(conditions)

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
        clear_monitoring_state()
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
