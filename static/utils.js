// Shared Utilities
const API_BASE = window.location.origin;

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function switchTab(tab, evt) {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => btn.classList.remove('active'));
    tabContents.forEach(content => content.classList.remove('active'));
    
    const e = evt || window.event;
    if (e && e.target) {
        e.target.classList.add('active');
    }
    document.getElementById(tab + 'Tab').classList.add('active');
}

function switchPage(page, evt) {
    const navTabs = document.querySelectorAll('.nav-tab');
    const pages = document.querySelectorAll('.page');
    
    navTabs.forEach(tab => tab.classList.remove('active'));
    pages.forEach(p => p.classList.remove('active'));
    
    const e = evt || window.event;
    if (e && e.target) {
        e.target.classList.add('active');
    }
    document.getElementById(page).classList.add('active');
}

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: { 
                'Content-Type': 'application/json',
                ...options.headers 
            },
            credentials: 'include',
            ...options
        });
        
        if (response.status === 401) {
            if (window.location.pathname !== '/login.html' && !window.location.pathname.endsWith('index.html')) {
                window.location.href = '/login.html';
            }
            return null;
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        return null;
    }
}
