"""
Authentication module - Handle user registration, login, password hashing
"""

import hashlib
import secrets
from modules.database import get_db

def hash_password(password):
    """Hash password with salt"""
    salt = secrets.token_hex(32)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return salt + '$' + pwd_hash.hex()

def verify_password(password, hash_with_salt):
    """Verify password against hash"""
    try:
        salt, pwd_hash = hash_with_salt.split('$')
        pwd_hash_verify = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return pwd_hash_verify.hex() == pwd_hash
    except:
        return False

def register_user(username, password):
    """Register a new user"""
    try:
        conn = get_db()
        c = conn.cursor()
        from datetime import datetime
        pwd_hash = hash_password(password)
        c.execute('INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)',
                  (username, pwd_hash, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error registering user: " + str(e))
        return False

def authenticate_user(username, password):
    """Authenticate user"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT password FROM users WHERE username = ?', (username,))
        result = c.fetchone()
        conn.close()
        
        if result and verify_password(password, result[0]):
            return True
        return False
    except Exception as e:
        print("Error authenticating user: " + str(e))
        return False

def login_required(f):
    """Decorator to require login"""
    from functools import wraps
    from flask import session, jsonify
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated_function
