"""
Modules package - Core functionality separated into logical modules
"""

from .database import init_db, get_setting, set_setting
from .auth import authenticate_user, register_user, login_required
from .currency import fetch_live_rates, fetch_historical_data, detect_trend
from .email_alert import send_email_alert
from .monitoring import start_monitoring, stop_monitoring, is_monitoring_active
from .routes import create_routes

__all__ = [
    'init_db',
    'get_setting',
    'set_setting',
    'authenticate_user',
    'register_user',
    'login_required',
    'fetch_live_rates',
    'fetch_historical_data',
    'detect_trend',
    'send_email_alert',
    'start_monitoring',
    'stop_monitoring',
    'is_monitoring_active',
    'create_routes'
]
