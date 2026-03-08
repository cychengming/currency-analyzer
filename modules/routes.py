"""
API Routes - All Flask endpoints
"""

import threading
import time
import uuid

from flask import Blueprint, jsonify, request, send_from_directory, session
from urllib.parse import unquote
from modules.auth import login_required, register_user, authenticate_user
from modules.database import (
    get_setting, set_setting, get_alert_history, clear_alert_history,
    get_all_alert_preferences, set_alert_preference, get_alert_preference,
    clear_monitoring_state, create_trade_journal_entry, close_trade_journal_entry,
    get_trade_journal_entries, get_trade_risk_summary, get_trade_journal_entry,
    update_trade_journal_entry
)
from modules.currency import fetch_live_rates, fetch_historical_data, fetch_historical_ohlc_data
from modules.email_alert import send_email_alert
from modules.backtest import run_backtest
from modules.dl_api import get_latest_forecast, get_forecast_by_run_id, list_forecast_runs

def create_routes(app, currency_pairs):
    """Create and register all API routes"""

    # DL job runner (in-memory)
    # Keeps the UI responsive while ingest/train run in background.
    dl_jobs = {}
    dl_jobs_lock = threading.Lock()

    def _dl_job_create(job_type: str, params: dict) -> str:
        job_id = uuid.uuid4().hex[:12]
        now = time.time()
        job = {
            'id': job_id,
            'type': job_type,
            'status': 'running',
            'message': 'starting',
            'params': params or {},
            'started_at': now,
            'finished_at': None,
            'result': None,
        }
        with dl_jobs_lock:
            dl_jobs[job_id] = job
            # Bound memory usage: keep last 50 jobs
            if len(dl_jobs) > 50:
                oldest = sorted(dl_jobs.values(), key=lambda j: j.get('started_at') or 0)[: max(0, len(dl_jobs) - 50)]
                for j in oldest:
                    dl_jobs.pop(j.get('id'), None)
        return job_id

    def _dl_job_update(job_id: str, **updates) -> None:
        with dl_jobs_lock:
            job = dl_jobs.get(job_id)
            if not job:
                return
            job.update(updates)

    def _dl_job_get(job_id: str):
        with dl_jobs_lock:
            job = dl_jobs.get(job_id)
            return dict(job) if job else None

    def _dl_run_in_thread(job_id: str, fn):
        def runner():
            try:
                _dl_job_update(job_id, message='running')
                result = fn()
                _dl_job_update(job_id, status='completed', message='completed', finished_at=time.time(), result=result)
            except BaseException as e:
                _dl_job_update(job_id, status='failed', message=str(e), finished_at=time.time())

        t = threading.Thread(target=runner, daemon=True)
        t.start()

    def _to_float(value, default=None):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    
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

    # ========== DL / FORECAST ROUTES (Optional) ==========

    @app.route('/api/dl/runs', methods=['GET'])
    @login_required
    def api_dl_runs():
        try:
            try:
                limit = int(request.args.get('limit', 25))
            except (TypeError, ValueError):
                limit = 25

            runs, err = list_forecast_runs(limit=limit)
            if err:
                return jsonify({'success': False, 'error': err}), 400
            return jsonify({'success': True, 'runs': runs})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/dl/forecast/latest', methods=['GET'])
    @login_required
    def api_dl_forecast_latest():
        try:
            asset = request.args.get('asset')
            asset = str(asset).strip() if asset is not None else None
            payload, err = get_latest_forecast(asset=asset)
            if err:
                return jsonify({'success': False, 'error': err}), 400
            return jsonify({'success': True, **payload})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/dl/forecast/<int:run_id>', methods=['GET'])
    @login_required
    def api_dl_forecast_by_id(run_id):
        try:
            payload, err = get_forecast_by_run_id(int(run_id))
            if err:
                return jsonify({'success': False, 'error': err}), 404
            return jsonify({'success': True, **payload})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/dl/job/<string:job_id>', methods=['GET'])
    @login_required
    def api_dl_job_status(job_id: str):
        job = _dl_job_get(str(job_id))
        if not job:
            return jsonify({'success': False, 'error': 'job not found'}), 404
        return jsonify({'success': True, 'job': job})

    @app.route('/api/dl/ingest', methods=['POST'])
    @login_required
    def api_dl_ingest():
        try:
            payload = request.json or {}
            years = payload.get('years', 30)
            try:
                years = int(years)
            except (TypeError, ValueError):
                years = 30
            years = max(1, min(int(years), 60))

            job_id = _dl_job_create('ingest', {'years': years})

            def work():
                from modules.dl_pipeline import ingest

                ingest(years=years)
                return f"ingested years={years}"

            _dl_run_in_thread(job_id, work)
            return jsonify({'success': True, 'job_id': job_id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/dl/train', methods=['POST'])
    @login_required
    def api_dl_train():
        try:
            payload = request.json or {}
            asset = payload.get('asset')
            asset = str(asset).strip() if asset is not None else 'GOLD/USD'
            model = str(payload.get('model', 'gru')).lower().strip()
            if model not in ('gru', 'lstm'):
                model = 'gru'

            lookback_days = payload.get('lookback_days', 120)
            horizon_days = payload.get('horizon_days', 365)
            try:
                lookback_days = int(lookback_days)
            except (TypeError, ValueError):
                lookback_days = 120
            try:
                horizon_days = int(horizon_days)
            except (TypeError, ValueError):
                horizon_days = 365

            lookback_days = max(10, min(int(lookback_days), 730))
            horizon_days = max(7, min(int(horizon_days), 730))

            job_id = _dl_job_create('train', {'asset': asset, 'model': model, 'lookback_days': lookback_days, 'horizon_days': horizon_days})

            def work():
                from modules.dl_pipeline import train

                run_id = train(model=model, lookback_days=lookback_days, horizon_days=horizon_days, asset=asset)
                return f"run_id={run_id}"

            _dl_run_in_thread(job_id, work)
            return jsonify({'success': True, 'job_id': job_id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/dl/ingest-train', methods=['POST'])
    @login_required
    def api_dl_ingest_train():
        try:
            payload = request.json or {}
            years = payload.get('years', 30)
            asset = payload.get('asset')
            asset = str(asset).strip() if asset is not None else 'GOLD/USD'
            model = str(payload.get('model', 'gru')).lower().strip()
            lookback_days = payload.get('lookback_days', 120)
            horizon_days = payload.get('horizon_days', 365)

            try:
                years = int(years)
            except (TypeError, ValueError):
                years = 30
            years = max(1, min(int(years), 60))

            if model not in ('gru', 'lstm'):
                model = 'gru'

            try:
                lookback_days = int(lookback_days)
            except (TypeError, ValueError):
                lookback_days = 120
            try:
                horizon_days = int(horizon_days)
            except (TypeError, ValueError):
                horizon_days = 365

            lookback_days = max(10, min(int(lookback_days), 730))
            horizon_days = max(7, min(int(horizon_days), 730))

            job_id = _dl_job_create(
                'ingest-train',
                {'years': years, 'asset': asset, 'model': model, 'lookback_days': lookback_days, 'horizon_days': horizon_days},
            )

            def work():
                from modules.dl_pipeline import ingest, train

                ingest(years=years)
                run_id = train(model=model, lookback_days=lookback_days, horizon_days=horizon_days, asset=asset)
                return f"run_id={run_id}"

            _dl_run_in_thread(job_id, work)
            return jsonify({'success': True, 'job_id': job_id})
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
                'monitoring_enabled': get_setting('monitoring_enabled', 'false') == 'true',
                'daily_risk_limit_pct': float(get_setting('daily_risk_limit_pct', 3.0)),
            }
            return jsonify(settings)

    # ========== TRADE RISK / DIARY ROUTES ==========

    @app.route('/api/trade/summary', methods=['GET'])
    @login_required
    def api_trade_summary():
        username = session.get('username')
        equity = _to_float(request.args.get('equity'), 0.0)
        planned_risk_usd = _to_float(request.args.get('planned_risk_usd'), 0.0)
        daily_limit_pct = _to_float(get_setting('daily_risk_limit_pct', 3.0), 3.0)
        summary = get_trade_risk_summary(username, equity, daily_limit_pct, planned_risk_usd)
        return jsonify(summary)

    @app.route('/api/trade/diary', methods=['GET', 'POST'])
    @login_required
    def api_trade_diary():
        username = session.get('username')

        if request.method == 'GET':
            try:
                limit = int(request.args.get('limit', 50))
            except (TypeError, ValueError):
                limit = 50
            limit = max(1, min(limit, 200))
            entries = get_trade_journal_entries(username, limit=limit)
            return jsonify({'success': True, 'entries': entries})

        data = request.json or {}
        pair = str(data.get('pair') or '').strip()
        side = str(data.get('side') or 'long').strip().lower()
        entry_reason = str(data.get('entry_reason') or '').strip()
        notes = str(data.get('notes') or '').strip()
        entry_price = _to_float(data.get('entry_price'))
        stop_price = _to_float(data.get('stop_price'))
        quantity = _to_float(data.get('quantity'))
        equity = _to_float(data.get('equity'), 0.0)
        atr = _to_float(data.get('atr'))
        sigma = _to_float(data.get('sigma'))

        if not pair:
            return jsonify({'success': False, 'error': 'pair is required'}), 400
        if side not in ('long', 'short'):
            return jsonify({'success': False, 'error': 'side must be long or short'}), 400
        if not entry_reason:
            return jsonify({'success': False, 'error': 'entry_reason is required'}), 400
        if entry_price is None or entry_price <= 0:
            return jsonify({'success': False, 'error': 'entry_price must be > 0'}), 400
        if stop_price is None or stop_price <= 0:
            return jsonify({'success': False, 'error': 'stop_price must be > 0'}), 400
        if quantity is None or quantity <= 0:
            return jsonify({'success': False, 'error': 'quantity must be > 0'}), 400

        if side == 'long' and stop_price >= entry_price:
            return jsonify({'success': False, 'error': 'For long trades, stop price must be below entry price'}), 400
        if side == 'short' and stop_price <= entry_price:
            return jsonify({'success': False, 'error': 'For short trades, stop price must be above entry price'}), 400

        risk_amount_usd = abs(entry_price - stop_price) * quantity
        if risk_amount_usd <= 0:
            return jsonify({'success': False, 'error': 'risk amount must be > 0'}), 400

        risk_pct_of_equity = None
        if equity and equity > 0:
            risk_pct_of_equity = (risk_amount_usd / equity) * 100.0

        daily_limit_pct = _to_float(get_setting('daily_risk_limit_pct', 3.0), 3.0)
        projected = get_trade_risk_summary(username, equity, daily_limit_pct, planned_risk_usd=risk_amount_usd)
        if not projected.get('can_open_new_trade', True):
            return jsonify({
                'success': False,
                'error': 'Daily risk limit exceeded. Reduce size or wait until tomorrow.',
                'summary': projected,
            }), 400

        entry = create_trade_journal_entry(
            username=username,
            pair=pair,
            side=side,
            entry_price=entry_price,
            stop_price=stop_price,
            quantity=quantity,
            risk_amount_usd=risk_amount_usd,
            risk_pct_of_equity=risk_pct_of_equity,
            atr=atr,
            sigma=sigma,
            entry_reason=entry_reason,
            notes=notes,
        )
        summary = get_trade_risk_summary(username, equity, daily_limit_pct)
        return jsonify({'success': True, 'entry': entry, 'summary': summary})

    @app.route('/api/trade/diary/<int:trade_id>/close', methods=['POST'])
    @login_required
    def api_trade_diary_close(trade_id):
        username = session.get('username')
        data = request.json or {}
        close_reason = str(data.get('close_reason') or '').strip()
        close_price = _to_float(data.get('close_price'))
        equity = _to_float(data.get('equity'), 0.0)

        if not close_reason:
            return jsonify({'success': False, 'error': 'close_reason is required'}), 400
        if close_price is not None and close_price <= 0:
            return jsonify({'success': False, 'error': 'close_price must be > 0'}), 400

        entry = close_trade_journal_entry(trade_id, username, close_price=close_price, close_reason=close_reason)
        if not entry:
            return jsonify({'success': False, 'error': 'trade not found'}), 404

        daily_limit_pct = _to_float(get_setting('daily_risk_limit_pct', 3.0), 3.0)
        summary = get_trade_risk_summary(username, equity, daily_limit_pct)
        return jsonify({'success': True, 'entry': entry, 'summary': summary})

    @app.route('/api/trade/diary/<int:trade_id>', methods=['PUT'])
    @login_required
    def api_trade_diary_update(trade_id):
        username = session.get('username')
        current = get_trade_journal_entry(trade_id, username)
        if not current:
            return jsonify({'success': False, 'error': 'trade not found'}), 404

        data = request.json or {}
        pair = str(data.get('pair', current.get('pair') or '')).strip()
        side = str(data.get('side', current.get('side') or 'long')).strip().lower()
        entry_reason = str(data.get('entry_reason', current.get('entry_reason') or '')).strip()
        notes = str(data.get('notes', current.get('notes') or '')).strip()
        entry_price = _to_float(data.get('entry_price'), _to_float(current.get('entry_price')))
        stop_price = _to_float(data.get('stop_price'), _to_float(current.get('stop_price')))
        quantity = _to_float(data.get('quantity'), _to_float(current.get('quantity')))
        equity = _to_float(data.get('equity'), 0.0)
        atr = _to_float(data.get('atr'), _to_float(current.get('atr')))
        sigma = _to_float(data.get('sigma'), _to_float(current.get('sigma')))
        status = str(current.get('status') or 'open')
        close_price = _to_float(data.get('close_price'), _to_float(current.get('close_price')))
        close_reason = str(data.get('close_reason', current.get('close_reason') or '')).strip()

        if not pair:
            return jsonify({'success': False, 'error': 'pair is required'}), 400
        if side not in ('long', 'short'):
            return jsonify({'success': False, 'error': 'side must be long or short'}), 400
        if not entry_reason:
            return jsonify({'success': False, 'error': 'entry_reason is required'}), 400
        if entry_price is None or entry_price <= 0:
            return jsonify({'success': False, 'error': 'entry_price must be > 0'}), 400
        if stop_price is None or stop_price <= 0:
            return jsonify({'success': False, 'error': 'stop_price must be > 0'}), 400
        if quantity is None or quantity <= 0:
            return jsonify({'success': False, 'error': 'quantity must be > 0'}), 400

        if side == 'long' and stop_price >= entry_price:
            return jsonify({'success': False, 'error': 'For long trades, stop price must be below entry price'}), 400
        if side == 'short' and stop_price <= entry_price:
            return jsonify({'success': False, 'error': 'For short trades, stop price must be above entry price'}), 400

        if status == 'closed' and not close_reason:
            return jsonify({'success': False, 'error': 'close_reason is required for closed trades'}), 400
        if close_price is not None and close_price <= 0:
            return jsonify({'success': False, 'error': 'close_price must be > 0'}), 400

        risk_amount_usd = abs(entry_price - stop_price) * quantity
        if risk_amount_usd <= 0:
            return jsonify({'success': False, 'error': 'risk amount must be > 0'}), 400

        risk_pct_of_equity = None
        if equity and equity > 0:
            risk_pct_of_equity = (risk_amount_usd / equity) * 100.0

        old_risk_amount_usd = _to_float(current.get('risk_amount_usd'), 0.0) or 0.0
        risk_delta_usd = risk_amount_usd - old_risk_amount_usd
        daily_limit_pct = _to_float(get_setting('daily_risk_limit_pct', 3.0), 3.0)
        projected = get_trade_risk_summary(username, equity, daily_limit_pct, planned_risk_usd=risk_delta_usd)
        if risk_delta_usd > 0 and not projected.get('can_open_new_trade', True):
            return jsonify({
                'success': False,
                'error': 'Editing this trade would exceed the daily risk limit.',
                'summary': projected,
            }), 400

        entry = update_trade_journal_entry(
            trade_id=trade_id,
            username=username,
            pair=pair,
            side=side,
            entry_price=entry_price,
            stop_price=stop_price,
            quantity=quantity,
            risk_amount_usd=risk_amount_usd,
            risk_pct_of_equity=risk_pct_of_equity,
            atr=atr,
            sigma=sigma,
            entry_reason=entry_reason,
            notes=notes,
            status=status,
            close_price=close_price,
            close_reason=close_reason,
            closed_at=current.get('closed_at'),
        )
        summary = get_trade_risk_summary(username, equity, daily_limit_pct)
        return jsonify({'success': True, 'entry': entry, 'summary': summary})

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
