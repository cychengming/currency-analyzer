// Authentication Module

async function handleLogin() {
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    
    try {
        const result = await fetchAPI('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        
        if (result.success) {
            window.location.href = '/dashboard.html';
        } else {
            document.getElementById('loginError').textContent = result.error;
        }
    } catch (error) {
        document.getElementById('loginError').textContent = 'Error logging in';
    }
}

async function handleRegister() {
    const username = document.getElementById('registerUsername').value;
    const password = document.getElementById('registerPassword').value;
    
    try {
        const result = await fetchAPI('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        
        if (result.success) {
            document.getElementById('registerError').textContent = '';
            document.getElementById('registerUsername').value = '';
            document.getElementById('registerPassword').value = '';
            document.getElementById('loginError').textContent = 'Registration successful! Please login.';
            switchTab('login');
        } else {
            document.getElementById('registerError').textContent = result.error;
        }
    } catch (error) {
        document.getElementById('registerError').textContent = 'Error registering';
    }
}

async function handleLogout() {
    try {
        await fetchAPI('/api/auth/logout', { method: 'POST' });
        window.location.href = '/login.html';
    } catch (error) {
        showToast('Error logging out', 'error');
    }
}

async function checkAuth() {
    try {
        const result = await fetchAPI('/api/auth/status');
        
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
