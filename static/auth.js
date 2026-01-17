// Authentication Module

async function handleLogin() {
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');
    
    if (!username || !password) {
        errorDiv.textContent = 'Please enter username and password';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ username, password })
        });
        
        const result = await response.json();
        
        if (result.success) {
            errorDiv.textContent = '';
            window.location.href = '/dashboard.html';
        } else {
            errorDiv.textContent = result.error || 'Login failed';
        }
    } catch (error) {
        console.error('Login error:', error);
        errorDiv.textContent = 'Error logging in: ' + error.message;
    }
}

async function handleRegister() {
    const username = document.getElementById('registerUsername').value;
    const password = document.getElementById('registerPassword').value;
    const errorDiv = document.getElementById('registerError');
    
    if (!username || !password) {
        errorDiv.textContent = 'Please enter username and password';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ username, password })
        });
        
        const result = await response.json();
        
        if (result.success) {
            errorDiv.textContent = '';
            document.getElementById('registerUsername').value = '';
            document.getElementById('registerPassword').value = '';
            document.getElementById('loginError').textContent = 'Registration successful! Please login.';
            switchTab('login');
        } else {
            errorDiv.textContent = result.error || 'Registration failed';
        }
    } catch (error) {
        console.error('Register error:', error);
        errorDiv.textContent = 'Error registering: ' + error.message;
    }
}

async function handleLogout() {
    try {
        await fetch(`${API_BASE}/api/auth/logout`, {
            method: 'POST',
            credentials: 'include'
        });
        window.location.href = '/login.html';
    } catch (error) {
        console.error('Logout error:', error);
        showToast('Error logging out', 'error');
    }
}

async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/api/auth/status`, {
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result && result.logged_in) {
            const userInfo = document.getElementById('userInfo');
            if (userInfo) {
                userInfo.textContent = `Logged in as: ${result.username}`;
            }
            return true;
        } else {
            if (window.location.pathname !== '/login.html' && !window.location.pathname.endsWith('index.html')) {
                window.location.href = '/login.html';
            }
            return false;
        }
    } catch (error) {
        console.error('Error checking auth:', error);
        return false;
    }
}

// Check auth on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('dashboard')) {
        checkAuth();
    }
});
