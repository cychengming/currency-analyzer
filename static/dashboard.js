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
            if (window.location.pathname !== '/login.html') {
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

let selectedPair = 'EUR/USD';
let currentTimeframe = 30;
let chart = null;
let liveRates = {};

async function initDashboard() {
    const authenticated = await checkAuth();
    if (!authenticated) return;
    
    loadPages();
    await loadSettings();
    await loadAlertPreferences();
    await refreshData();
    
    setInterval(refreshData, 60000);
}

function loadPages() {
    const container = document.getElementById('pagesContainer');
    
    container.innerHTML = `
        <!-- Overview Page -->
        <div id="overview" class="page active">
            <div class="grid-2">
                <div class="card">
                    <h2 class="card-title">Live Exchange Rates</h2>
                    <div class="rates-grid" id="ratesGrid">
                        <div class="loading">Loading rates...</div>
                    </div>
                </div>
                
                <div class="card">
                    <h2 class="card-title">Recent Alerts</h2>
                    <div class="alert-list" id="recentAlerts">
                        <div class="loading">No alerts yet</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2 class="card-title"><span id="selectedPair">EUR/USD</span> Historical Chart</h2>
                <div class="chart-container">
                    <canvas id="priceChart"></canvas>
                </div>
            </div>
        </div>
        
        <!-- Alert History Page -->
        <div id="alerts" class="page">
            <div class="card">
                <h2 class="card-title">Complete Alert History</h2>
                <div class="alert-list" id="alertHistory">
                    <div class="loading">No alerts yet</div>
                </div>
                <div style="margin-top: 20px;">
                    <button class="btn-danger" onclick="clearAlertHistory()">Clear All Alerts</button>
                </div>
            </div>
        </div>
        
        <!-- Manage Alerts Page -->
        <div id="manage" class="page">
            <div class="card">
                <h2 class="card-title">Alert Preferences by Pair</h2>
                <div id="alertPreferencesContainer" class="preferences-grid">
                    <div class="loading">Loading preferences...</div>
                </div>
            </div>
        </div>
        
        <!-- Settings Page -->
        <div id="settings" class="page">
            <div class="card">
                <h2 class="card-title">Settings</h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div class="form-group">
                        <label>Trend Threshold (%)</label>
                        <input type="number" id="trendThreshold" min="0.5" max="10" step="0.5" value="2">
                    </div>
                    <div class="form-group">
                        <label>Detection Period (days)</label>
                        <select id="detectionPeriod">
                            <option value="7">7 days</option>
                            <option value="14">14 days</option>
                            <option value="30" selected>30 days</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Check Interval</label>
                        <select id="checkInterval">
                            <option value="300">Every 5 minutes</option>
                            <option value="900" selected>Every 15 minutes</option>
                            <option value="1800">Every 30 minutes</option>
                            <option value="3600">Every hour</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Alert Email</label>
                        <input type="email" id="alertEmail" placeholder="your.email@gmail.com">
                    </div>
                </div>
                <div style="margin-top: 20px; display: flex; gap: 12px;">
                    <button class="btn-primary" style="width: auto; flex: 1;" onclick="saveSettings()">Save Settings</button>
                    <button class="btn-secondary" style="width: auto; flex: 1;" onclick="testEmail()">Test Email</button>
                </div>
            </div>
        </div>
    `;
}

async function refreshData() {
    await Promise.all([
        fetchLiveRates(),
        fetchHistoricalData(),
        fetchAlerts(),
        updateMonitoringStatus()
    ]);
}

async function fetchLiveRates() {
    const rates = await fetchAPI('/api/live-rates');
    if (rates) {
        liveRates = rates;
        renderRates();
    }
}

function renderRates() {
    const grid = document.getElementById('ratesGrid');
    const pairs = Object.keys(liveRates);
    
    if (pairs.length === 0) {
        grid.innerHTML = '<div class="loading">No data available</div>';
        return;
    }
    
    grid.innerHTML = pairs.map(pair => {
        const data = liveRates[pair];
        const isPositive = data.change >= 0;
        const isSelected = pair === selectedPair;
        
        return `
            <div class="rate-card ${isSelected ? 'selected' : ''}" onclick="selectPair('${pair}')">
                <div class="rate-pair">${pair}</div>
                <div class="rate-value">${data.rate.toFixed(4)}</div>
                <div class="rate-change ${isPositive ? 'positive' : 'negative'}">
                    ${isPositive ? '+' : ''}${data.change.toFixed(4)} (${isPositive ? '+' : ''}${data.changePercent.toFixed(2)}%)
                </div>
            </div>
        `;
    }).join('');
}

async function selectPair(pair) {
    selectedPair = pair;
    document.getElementById('selectedPair').textContent = pair;
    renderRates();
    await fetchHistoricalData();
}

async function fetchHistoricalData() {
    const data = await fetchAPI(`/api/historical/${selectedPair}/${currentTimeframe}`);
    if (data) {
        updateChart(data);
    }
}

function updateChart(data) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    if (chart) chart.destroy();
    
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [{
                label: selectedPair,
                data: data.map(d => d.rate),
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.1,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#f1f5f9' } }
            },
            scales: {
                y: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: '#334155' }
                },
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: '#334155' }
                }
            }
        }
    });
}

async function fetchAlerts() {
    const alerts = await fetchAPI('/api/alerts');
    if (alerts) {
        renderAlerts(alerts);
    }
}

function renderAlerts(alerts) {
    const recentAlerts = document.getElementById('recentAlerts');
    const alertHistory = document.getElementById('alertHistory');
    
    const content = alerts.length === 0 
        ? '<div class="loading">No alerts yet</div>'
        : alerts.map(alert => `
            <div class="alert-item">
                <div class="alert-header">
                    <span class="alert-pair">${alert.pair}</span>
                    <span class="alert-change">+${alert.percent_change}%</span>
                </div>
                <div style="font-size: 14px; color: #cbd5e1;">
                    ${alert.old_rate} → ${alert.new_rate}
                </div>
                <div class="alert-time">${new Date(alert.timestamp).toLocaleString()}</div>
            </div>
        `).join('');
    
    if (recentAlerts) {
        recentAlerts.innerHTML = alerts.length === 0 
            ? '<div class="loading">No recent alerts</div>'
            : alerts.slice(0, 5).map(alert => `
                <div class="alert-item">
                    <div class="alert-header">
                        <span class="alert-pair">${alert.pair}</span>
                        <span class="alert-change">+${alert.percent_change}%</span>
                    </div>
                    <div style="font-size: 12px; color: #94a3b8;">
                        ${new Date(alert.timestamp).toLocaleString()}
                    </div>
                </div>
            `).join('');
    }
    
    if (alertHistory) {
        alertHistory.innerHTML = content;
    }
}

async function loadSettings() {
    const settings = await fetchAPI('/api/settings');
    if (settings) {
        document.getElementById('trendThreshold').value = settings.trend_threshold;
        document.getElementById('detectionPeriod').value = settings.detection_period;
        document.getElementById('checkInterval').value = settings.check_interval;
        document.getElementById('alertEmail').value = settings.alert_email;
    }
}

async function saveSettings() {
    const settings = {
        trend_threshold: document.getElementById('trendThreshold').value,
        detection_period: document.getElementById('detectionPeriod').value,
        check_interval: document.getElementById('checkInterval').value,
        alert_email: document.getElementById('alertEmail').value
    };
    
    const result = await fetchAPI('/api/settings', {
        method: 'POST',
        body: JSON.stringify(settings)
    });
    
    if (result && result.success) {
        showToast('Settings saved successfully!', 'success');
    }
}

async function testEmail() {
    const result = await fetchAPI('/api/test-email', { method: 'POST' });
    
    if (result) {
        if (result.success) {
            showToast(result.message, 'success');
        } else {
            showToast(result.error, 'error');
        }
    }
}

async function loadAlertPreferences() {
    const preferences = await fetchAPI('/api/alerts/preferences');
    if (preferences) {
        renderAlertPreferences(preferences);
    }
}

function renderAlertPreferences(preferences) {
    const container = document.getElementById('alertPreferencesContainer');
    
    const pairs = Object.keys(preferences).sort();
    container.innerHTML = pairs.map(pair => {
        const pref = preferences[pair];
        return `
            <div class="pref-item">
                <div class="form-group">
                    <label style="margin-bottom: 4px;">Pair</label>
                    <input type="text" value="${pair}" disabled style="background: #1e293b;">
                </div>
                <div class="form-group">
                    <label style="margin-bottom: 4px;">Threshold (%)</label>
                    <input type="number" id="threshold-${pair}" min="0.1" max="20" step="0.1" 
                           value="${pref.custom_threshold || ''}" placeholder="Use default">
                </div>
                <div class="form-group">
                    <label style="margin-bottom: 4px;">Period (days)</label>
                    <input type="number" id="period-${pair}" min="1" max="365" 
                           value="${pref.custom_period || ''}" placeholder="Use default">
                </div>
                <div style="display: flex; gap: 8px;">
                    <label style="display: flex; align-items: center; gap: 8px; margin: 0; cursor: pointer;">
                        <input type="checkbox" id="enabled-${pair}" ${pref.enabled ? 'checked' : ''} style="width: auto;">
                        <span>Enabled</span>
                    </label>
                    <button class="btn-success" style="padding: 8px 12px; font-size: 12px;" 
                            onclick="saveAlertPreference('${pair}')">Save</button>
                </div>
            </div>
        `;
    }).join('');
}

async function saveAlertPreference(pair) {
    const enabled = document.getElementById(`enabled-${pair}`).checked;
    const thresholdValue = document.getElementById(`threshold-${pair}`).value;
    const periodValue = document.getElementById(`period-${pair}`).value;
    
    const data = {
        pair: pair,
        enabled: enabled,
        custom_threshold: thresholdValue ? parseFloat(thresholdValue) : null,
        custom_period: periodValue ? parseInt(periodValue) : null
    };
    
    const result = await fetchAPI('/api/alerts/preferences', {
        method: 'POST',
        body: JSON.stringify(data)
    });
    
    if (result && result.success) {
        showToast(`Preferences saved for ${pair}!`, 'success');
        await loadAlertPreferences();
    }
}

async function clearAlertHistory() {
    if (!confirm('Are you sure you want to clear all alert history?')) return;
    
    const result = await fetchAPI('/api/alerts/clear', {
        method: 'DELETE'
    });
    
    if (result && result.success) {
        showToast('Alert history cleared!', 'success');
        await fetchAlerts();
    }
}

async function startMonitoring() {
    const result = await fetchAPI('/api/monitoring/start', { method: 'POST' });
    if (result && result.success) {
        updateMonitoringStatus();
        showToast('Monitoring started!', 'success');
    }
}

async function stopMonitoring() {
    const result = await fetchAPI('/api/monitoring/stop', { method: 'POST' });
    if (result && result.success) {
        updateMonitoringStatus();
        showToast('Monitoring stopped', 'success');
    }
}

async function updateMonitoringStatus() {
    const status = await fetchAPI('/api/monitoring/status');
    
    if (status) {
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        
        if (status.active) {
            dot.classList.add('active');
            text.textContent = 'Monitoring Active';
            startBtn.style.display = 'none';
            stopBtn.style.display = 'block';
        } else {
            dot.classList.remove('active');
            text.textContent = 'Monitoring Inactive';
            startBtn.style.display = 'block';
            stopBtn.style.display = 'none';
        }
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', initDashboard);
