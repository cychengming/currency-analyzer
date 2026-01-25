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
let timeframeUnit = 'days';
let timeframeValue = 30;
let chart = null;
let liveRates = {};

// Backtest state
let btConditions = null;
let btAvailablePairs = [];
let btSeriesOHLC = [];
let btResult = null;
let btSelectedTradeIndex = null;
let btTradeChart = null;

async function initDashboard() {
    const authenticated = await checkAuth();
    if (!authenticated) return;
    
    // Show dashboard
    const dashboard = document.getElementById('dashboard');
    if (dashboard) {
        dashboard.classList.add('show');
    }
    
    loadPages();
    initTimeframeControls();
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
                <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
                    <h2 class="card-title" style="margin:0;"><span id="selectedPair">EUR/USD</span> Historical Chart</h2>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <label for="timeframeUnit" style="font-size: 13px; color: #94a3b8;">Unit</label>
                        <select id="timeframeUnit" onchange="changeTimeframeUnit()">
                            <option value="days" selected>Days</option>
                            <option value="weeks">Weeks</option>
                            <option value="months">Months</option>
                        </select>
                        <label for="timeframeValue" style="font-size: 13px; color: #94a3b8;">Value</label>
                        <select id="timeframeValue" onchange="changeTimeframeValue()"></select>
                    </div>
                </div>
                <div class="chart-container">
                    <canvas id="priceChart"></canvas>
                    <div id="chartEmpty" class="loading" style="display:none;">No historical data available</div>
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
                <p style="color: #94a3b8; margin-bottom: 20px; font-size: 14px;">
                    Configure multiple alert types per currency pair. Choose from 6 different alert conditions.
                </p>
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

        <!-- Backtest Page -->
        <div id="backtest" class="page">
            <div class="card">
                <h2 class="card-title">Backtest</h2>
                <p style="color: #94a3b8; margin-bottom: 12px; font-size: 14px;">
                    Run a simple entry/exit backtest on daily OHLC bars. Click a trade row to see entry/exit markers on the chart.
                </p>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                    <div class="form-group">
                        <label>Pair</label>
                        <select id="btPair"></select>
                    </div>
                    <div class="form-group">
                        <label>History Window (days)</label>
                        <input type="number" id="btDays" min="30" step="1" value="730">
                    </div>
                    <div class="form-group">
                        <label>Initial Capital</label>
                        <input type="number" id="btInitialCapital" min="0" step="100" value="10000">
                    </div>
                    <div class="form-group">
                        <label style="margin-bottom: 4px;">Multiple Trades</label>
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="btAllowMultiple" checked style="width: auto;">
                            <span>Allow multiple entries</span>
                        </label>
                    </div>
                </div>

                <div style="margin-top: 14px; padding-top: 14px; border-top: 1px solid #334155;">
                    <h3 style="margin-bottom: 10px;">Entry Rule</h3>
                    <div class="form-group">
                        <label>Entry Type</label>
                        <select id="btEntryType"></select>
                    </div>
                    <div id="btEntryParams" style="margin-top: 12px;"></div>
                </div>

                <div style="margin-top: 14px; padding-top: 14px; border-top: 1px solid #334155;">
                    <h3 style="margin-bottom: 10px;">Exit Rules</h3>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;">
                        <div class="form-group">
                            <label>Max Holding Days</label>
                            <input type="number" id="btExitMaxDays" min="1" step="1" value="60">
                        </div>
                        <div class="form-group">
                            <label>Stop Loss (%)</label>
                            <input type="number" id="btExitStopLossPct" min="0" step="0.1" value="5">
                        </div>
                        <div class="form-group">
                            <label>Take Profit (%)</label>
                            <input type="number" id="btExitTakeProfitPct" min="0" step="0.1" value="10">
                        </div>
                    </div>

                    <div style="margin-top: 10px;">
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="btUseExitSignal" style="width: auto;">
                            <span>Enable exit-by-signal</span>
                        </label>
                        <div id="btExitSignalBlock" style="display:none; margin-top: 10px;">
                            <div class="form-group">
                                <label>Exit Signal Type</label>
                                <select id="btExitSignalType"></select>
                            </div>
                            <div id="btExitSignalParams" style="margin-top: 12px;"></div>
                        </div>
                    </div>
                </div>

                <div id="btError" class="loading" style="display:none; color: #fca5a5; margin-top: 10px;"></div>

                <div style="display:flex; gap: 10px; margin-top: 16px;">
                    <button class="btn-success" id="btRunBtn" onclick="runBacktest()">Run Backtest</button>
                    <button class="btn-secondary" onclick="setBacktestPairToSelected()">Use Selected Pair</button>
                </div>
            </div>

            <div class="card" id="btResultsCard" style="display:none; margin-top: 16px;">
                <h2 class="card-title">Results</h2>
                <div id="btSummary" style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 12px;"></div>
                <div id="btTrades" style="margin-top: 14px;"></div>
                <div id="btTradeDetail" style="margin-top: 14px; padding-top: 14px; border-top: 1px solid #334155;">
                    <h3 style="margin-bottom: 10px;">Trade Detail</h3>
                    <div id="btTradeDetailHeader" style="color: #94a3b8; font-size: 13px; margin-bottom: 10px;"></div>
                    <div style="display:grid; grid-template-columns: 2fr 1fr 1fr; gap: 12px; align-items: end; margin-bottom: 10px;">
                        <div style="color: #cbd5e1; font-size: 13px;" id="btTradeDetailTitle"></div>
                        <div class="form-group" style="margin:0;">
                            <label>Chart Scope</label>
                            <select id="btTradeScope" onchange="renderSelectedTradeChart()">
                                <option value="window" selected>Window around trade</option>
                                <option value="full">Whole history</option>
                            </select>
                        </div>
                        <div class="form-group" style="margin:0;">
                            <label>Window Padding (days)</label>
                            <select id="btTradeWindowDays" onchange="renderSelectedTradeChart()">
                                <option value="10">10</option>
                                <option value="20">20</option>
                                <option value="30" selected>30</option>
                                <option value="60">60</option>
                                <option value="90">90</option>
                                <option value="180">180</option>
                            </select>
                        </div>
                    </div>
                    <div style="height: 340px; position: relative;">
                        <canvas id="btTradeChart"></canvas>
                        <div id="btTradeChartEmpty" class="loading" style="display:none; color:#94a3b8; padding: 10px;">Loading signal series...</div>
                    </div>
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

        // Update backtest pairs list
        btAvailablePairs = Object.keys(liveRates || {}).sort();
        renderBacktestPairOptions();
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

    // Keep backtest pair in sync if user wants it
    const btPairEl = document.getElementById('btPair');
    if (btPairEl && btPairEl.value !== pair) {
        // do not force overwrite; the button exists for that.
    }
}

function supportedBacktestTypes(conditions) {
    const allow = new Set(['long_term_uptrend', 'percentage_change', 'moving_average', 'price_level']);
    const out = [];
    for (const k of Object.keys(conditions || {})) {
        if (allow.has(k)) out.push(k);
    }
    const pref = ['long_term_uptrend', 'percentage_change', 'moving_average', 'price_level'];
    out.sort((a, b) => pref.indexOf(a) - pref.indexOf(b));
    return out;
}

function renderBacktestPairOptions() {
    const el = document.getElementById('btPair');
    if (!el) return;
    const pairs = (btAvailablePairs && btAvailablePairs.length) ? btAvailablePairs : [selectedPair];
    const current = el.value || selectedPair;
    el.innerHTML = pairs.map(p => `<option value="${p}" ${p === current ? 'selected' : ''}>${p}</option>`).join('');
    if (!el.value && selectedPair) el.value = selectedPair;
}

function renderBacktestTypeOptions() {
    const entryEl = document.getElementById('btEntryType');
    const exitEl = document.getElementById('btExitSignalType');
    if (!entryEl || !exitEl || !btConditions) return;

    const types = supportedBacktestTypes(btConditions);
    const toOpt = (t) => {
        const name = btConditions[t] && btConditions[t].name ? btConditions[t].name : t;
        return `<option value="${t}">${name}</option>`;
    };

    entryEl.innerHTML = types.map(toOpt).join('');
    exitEl.innerHTML = types.map(toOpt).join('');

    // Defaults
    if (types.includes('long_term_uptrend')) entryEl.value = 'long_term_uptrend';
    else if (types.length) entryEl.value = types[0];

    if (types.includes('moving_average')) exitEl.value = 'moving_average';
    else if (types.length) exitEl.value = types[0];

    entryEl.onchange = () => renderBacktestParamInputs('btEntryParams', entryEl.value, 'bt-entry');
    exitEl.onchange = () => renderBacktestParamInputs('btExitSignalParams', exitEl.value, 'bt-exit-signal');
}

function renderBacktestParamInputs(containerId, typeKey, prefix) {
    const container = document.getElementById(containerId);
    if (!container || !btConditions) return;
    const cfg = btConditions[typeKey] || { parameters: {} };
    const params = cfg.parameters || {};
    const entries = Object.entries(params);
    if (!entries.length) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = entries.map(([paramName, paramConfig]) => {
        const label = `${paramName.replace(/_/g, ' ')}${paramConfig.unit ? ' (' + paramConfig.unit + ')' : ''}`;
        const id = `${prefix}-${paramName}`;
        const def = (paramConfig && paramConfig.default !== undefined) ? paramConfig.default : '';

        if (paramConfig.type === 'boolean') {
            const checked = def ? 'checked' : '';
            return `
                <div class="form-group" style="margin-bottom: 12px;">
                    <label style="margin-bottom: 4px; font-size: 13px;">${label}</label>
                    <label style="display:flex; align-items:center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="${id}" ${checked} style="width:auto;">
                        <span>Enabled</span>
                    </label>
                </div>
            `;
        }

        if (paramConfig.type === 'select') {
            const opts = (paramConfig.options || []).map(opt => {
                const sel = (opt === def) ? 'selected' : '';
                return `<option value="${opt}" ${sel}>${opt}</option>`;
            }).join('');
            return `
                <div class="form-group" style="margin-bottom: 12px;">
                    <label style="margin-bottom: 4px; font-size: 13px;">${label}</label>
                    <select id="${id}" style="width: 100%; padding: 8px; background: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #f1f5f9;">
                        ${opts}
                    </select>
                </div>
            `;
        }

        const min = (paramConfig.min !== undefined) ? paramConfig.min : 0;
        const max = (paramConfig.max !== undefined) ? paramConfig.max : 999999;
        const step = (paramConfig.step !== undefined) ? paramConfig.step : 0.1;
        return `
            <div class="form-group" style="margin-bottom: 12px;">
                <label style="margin-bottom: 4px; font-size: 13px;">${label}</label>
                <input type="number" id="${id}" min="${min}" max="${max}" step="${step}" value="${def}" placeholder="Default: ${def}">
            </div>
        `;
    }).join('');
}

function initBacktestControls() {
    const useExit = document.getElementById('btUseExitSignal');
    const block = document.getElementById('btExitSignalBlock');
    if (useExit && block) {
        useExit.onchange = () => {
            block.style.display = useExit.checked ? 'block' : 'none';
        };
    }

    renderBacktestPairOptions();
    renderBacktestTypeOptions();
    const entryType = document.getElementById('btEntryType');
    const exitType = document.getElementById('btExitSignalType');
    if (entryType) renderBacktestParamInputs('btEntryParams', entryType.value, 'bt-entry');
    if (exitType) renderBacktestParamInputs('btExitSignalParams', exitType.value, 'bt-exit-signal');
}

function setBacktestPairToSelected() {
    const el = document.getElementById('btPair');
    if (!el) return;
    el.value = selectedPair;
    showToast('Backtest pair set to selected pair', 'success');
}

function btShowError(msg) {
    const el = document.getElementById('btError');
    if (!el) return;
    el.textContent = msg || '';
    el.style.display = msg ? 'block' : 'none';
}

function btSetRunning(running) {
    const btn = document.getElementById('btRunBtn');
    if (!btn) return;
    btn.disabled = !!running;
    btn.textContent = running ? 'Running...' : 'Run Backtest';
}

async function fetchHistoricalOHLCFor(pair, days) {
    try {
        const encodedPair = encodeURIComponent(pair);
        const d = Number(days);
        if (!pair || !Number.isFinite(d) || d <= 0) return [];
        const result = await fetchAPI(`/api/historical-ohlc/${encodedPair}/${d}`);
        if (!Array.isArray(result)) return [];
        return result.filter(item =>
            item && item.date &&
            (
                (item.open !== undefined && item.high !== undefined && item.low !== undefined && item.close !== undefined) ||
                item.rate !== undefined
            )
        ).map(item => {
            const rate = Number(item.rate);
            const open = (item.open !== undefined) ? Number(item.open) : rate;
            const high = (item.high !== undefined) ? Number(item.high) : rate;
            const low = (item.low !== undefined) ? Number(item.low) : rate;
            const close = (item.close !== undefined) ? Number(item.close) : rate;

            return {
                date: item.date,
                open,
                high,
                low,
                close,
            };
        }).filter(item =>
            item.date &&
            Number.isFinite(item.open) && Number.isFinite(item.high) &&
            Number.isFinite(item.low) && Number.isFinite(item.close)
        );
    } catch (e) {
        console.error(e);
        return [];
    }
}

async function runBacktest() {
    if (!btConditions) {
        showToast('Conditions not loaded yet', 'error');
        return;
    }

    btShowError('');
    btSetRunning(true);
    const resultsCard = document.getElementById('btResultsCard');
    if (resultsCard) resultsCard.style.display = 'none';

    try {
        const types = supportedBacktestTypes(btConditions);
        const pair = document.getElementById('btPair')?.value || selectedPair;
        const days = Number(document.getElementById('btDays')?.value || 730);
        const initialCapital = Number(document.getElementById('btInitialCapital')?.value || 10000);
        const allowMultiple = !!document.getElementById('btAllowMultiple')?.checked;

        const entryType = document.getElementById('btEntryType')?.value;
        if (!types.includes(entryType)) throw new Error('Unsupported entry type: ' + entryType);

        const entryCfg = btConditions[entryType] || { parameters: {} };
        const entryParamsCfg = entryCfg.parameters || {};
        const entry = { type: entryType };
        for (const [p, pcfg] of Object.entries(entryParamsCfg)) {
            const id = `bt-entry-${p}`;
            const el = document.getElementById(id);
            if (!el) {
                entry[p] = pcfg.default ?? null;
                continue;
            }
            if (pcfg.type === 'boolean') entry[p] = !!el.checked;
            else if (pcfg.type === 'number') {
                const v = parseFloat(el.value);
                entry[p] = isNaN(v) ? (pcfg.default ?? null) : v;
            } else entry[p] = el.value || (pcfg.default ?? null);
        }

        const exitCfg = {
            max_holding_days: Number(document.getElementById('btExitMaxDays')?.value || 60),
            stop_loss_pct: Number(document.getElementById('btExitStopLossPct')?.value || 5),
            take_profit_pct: Number(document.getElementById('btExitTakeProfitPct')?.value || 10),
        };

        const useExitSignal = !!document.getElementById('btUseExitSignal')?.checked;
        if (useExitSignal) {
            const exitSignalType = document.getElementById('btExitSignalType')?.value;
            if (!types.includes(exitSignalType)) throw new Error('Unsupported exit signal type: ' + exitSignalType);
            const escfg = btConditions[exitSignalType] || { parameters: {} };
            const esp = escfg.parameters || {};
            const signal = { type: exitSignalType };
            for (const [p, pcfg] of Object.entries(esp)) {
                const id = `bt-exit-signal-${p}`;
                const el = document.getElementById(id);
                if (!el) {
                    signal[p] = pcfg.default ?? null;
                    continue;
                }
                if (pcfg.type === 'boolean') signal[p] = !!el.checked;
                else if (pcfg.type === 'number') {
                    const v = parseFloat(el.value);
                    signal[p] = isNaN(v) ? (pcfg.default ?? null) : v;
                } else signal[p] = el.value || (pcfg.default ?? null);
            }
            exitCfg.signal = signal;
        }

        const payload = {
            pair,
            days,
            entry,
            exit: exitCfg,
            initial_capital: initialCapital,
            allow_multiple_trades: allowMultiple,
        };

        const result = await fetchAPI('/api/backtest', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        if (!result || !result.success) {
            const msg = (result && (result.error || result.message)) ? (result.error || result.message) : 'Backtest failed';
            btShowError(msg);
            showToast(msg, 'error');
            return;
        }

        btResult = result;
        btSelectedTradeIndex = (Array.isArray(result.trades) && result.trades.length) ? 0 : null;

        // Preload OHLC series
        const maxDays = 3650;
        const preloadDays = Math.max(30, Math.min(Number(days) || 365, maxDays));
        btSeriesOHLC = [];
        const empty = document.getElementById('btTradeChartEmpty');
        if (empty) empty.style.display = 'block';
        btSeriesOHLC = await fetchHistoricalOHLCFor(pair, preloadDays);
        if (empty) empty.style.display = btSeriesOHLC.length ? 'none' : 'block';

        renderBacktestResults();
        showToast('Backtest complete', 'success');
    } catch (e) {
        const msg = (e && e.message) ? e.message : String(e);
        btShowError(msg);
        showToast(msg, 'error');
    } finally {
        btSetRunning(false);
    }
}

function renderBacktestResults() {
    const card = document.getElementById('btResultsCard');
    if (!card) return;
    card.style.display = (btResult && btResult.success) ? 'block' : 'none';
    if (!btResult || !btResult.success) return;

    const summary = btResult.summary || {};
    const summaryEl = document.getElementById('btSummary');
    if (summaryEl) {
        const stat = (label, value) => `
            <div class="bt-stat">
                <div class="bt-stat-label">${label}</div>
                <div class="bt-stat-value">${value}</div>
            </div>
        `;
        summaryEl.innerHTML = [
            stat('Trades', String(summary.num_trades ?? 0)),
            stat('Win Rate', String(summary.win_rate_pct ?? 0) + '%'),
            stat('Avg Trade', String(summary.avg_trade_pnl_pct ?? 0) + '%'),
            stat('Total Return', String(summary.total_return_pct ?? 0) + '%'),
            stat('Final Equity', String(summary.final_equity ?? 0)),
            stat('Max Drawdown', String(summary.max_drawdown_pct ?? 0) + '%'),
        ].join('');
    }

    const tradesEl = document.getElementById('btTrades');
    const trades = Array.isArray(btResult.trades) ? btResult.trades : [];
    if (tradesEl) {
        if (!trades.length) {
            tradesEl.innerHTML = '<div class="loading">No trades generated by this rule set</div>';
        } else {
            tradesEl.innerHTML = `
                <div style="color: #94a3b8; font-size: 13px; margin-bottom: 8px;">Tip: click a trade row to view the entry/exit chart.</div>
                <table class="bt-table">
                    <thead>
                        <tr>
                            <th>Entry Date</th>
                            <th>Entry</th>
                            <th>Exit Date</th>
                            <th>Exit</th>
                            <th>PnL %</th>
                            <th>Days</th>
                            <th>Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${trades.map((t, idx) => {
                            const pnl = Number(t.pnl_pct) || 0;
                            const cls = pnl >= 0 ? 'pos' : 'neg';
                            const selected = (btSelectedTradeIndex === idx);
                            return `
                                <tr class="bt-trade-row${selected ? ' selected' : ''}" onclick="selectTrade(${idx})">
                                    <td>${t.entry_date}</td>
                                    <td>${t.entry_price}</td>
                                    <td>${t.exit_date}</td>
                                    <td>${t.exit_price}</td>
                                    <td class="bt-pnl ${cls}">${t.pnl_pct}</td>
                                    <td>${t.holding_days}</td>
                                    <td>${t.exit_reason}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            `;
        }
    }

    renderSelectedTradeChart();
}

function selectTrade(idx) {
    btSelectedTradeIndex = idx;
    renderBacktestResults();
}

function renderSelectedTradeChart() {
    const titleEl = document.getElementById('btTradeDetailTitle');
    const headerEl = document.getElementById('btTradeDetailHeader');
    const emptyEl = document.getElementById('btTradeChartEmpty');
    const canvas = document.getElementById('btTradeChart');

    if (!titleEl || !headerEl || !canvas) return;
    const trades = (btResult && btResult.success && Array.isArray(btResult.trades)) ? btResult.trades : [];
    if (!trades.length || btSelectedTradeIndex === null || btSelectedTradeIndex === undefined) {
        headerEl.textContent = 'Select a trade above to see the chart.';
        titleEl.textContent = '';
        if (btTradeChart) {
            btTradeChart.destroy();
            btTradeChart = null;
        }
        return;
    }

    const t = trades[btSelectedTradeIndex];
    if (!t) return;

    headerEl.textContent = '';
    titleEl.textContent = `${document.getElementById('btPair')?.value || selectedPair} | ${t.entry_date} → ${t.exit_date} | PnL ${t.pnl_pct}% (${t.exit_reason})`;

    if (!Array.isArray(btSeriesOHLC) || !btSeriesOHLC.length) {
        if (emptyEl) emptyEl.style.display = 'block';
        return;
    }
    if (emptyEl) emptyEl.style.display = 'none';

    const findIndexForDate = (dateStr) => {
        if (!dateStr) return -1;
        const exact = btSeriesOHLC.findIndex(d => d && d.date === dateStr);
        if (exact !== -1) return exact;
        const fallback = btSeriesOHLC.findIndex(d => d && d.date && d.date >= dateStr);
        return fallback;
    };

    const entryIdx = findIndexForDate(t.entry_date);
    const exitIdx = findIndexForDate(t.exit_date);
    if (entryIdx < 0 || exitIdx < 0) return;

    const scope = (document.getElementById('btTradeScope')?.value || 'window');
    const pad = Number(document.getElementById('btTradeWindowDays')?.value || 30);

    // Choose which price series to display (whole history vs trade window).
    let workingSeries = btSeriesOHLC;
    if (scope !== 'full') {
        const lo = Math.min(entryIdx, exitIdx);
        const hi = Math.max(entryIdx, exitIdx);
        const p = Math.max(5, pad);
        const start = Math.max(0, lo - p);
        const end = Math.min(btSeriesOHLC.length - 1, hi + p);
        workingSeries = btSeriesOHLC.slice(start, end + 1);
    }

    // Keep entry/exit dates exactly as reported by the backtest.
    // If the trade dates fall on non-trading days (weekends/holidays), insert a synthetic bar
    // (copied from the nearest available bar) so the chart can show the exact date label.
    const hasDate = (series, dateStr) => series.some(d => d && d.date === dateStr);
    const barForDate = (dateStr) => {
        const idx = findIndexForDate(dateStr);
        if (idx < 0) return null;
        return btSeriesOHLC[idx];
    };

    const insertSyntheticIfNeeded = (series, dateStr) => {
        if (!dateStr || hasDate(series, dateStr)) return series;
        const ref = barForDate(dateStr);
        if (!ref) return series;
        const synthetic = {
            date: dateStr,
            open: Number(ref.open),
            high: Number(ref.high),
            low: Number(ref.low),
            close: Number(ref.close),
            __synthetic: true,
        };
        const next = series.concat([synthetic]);
        next.sort((a, b) => String(a.date).localeCompare(String(b.date)));
        return next;
    };

    const beforeInsertLen = workingSeries.length;
    workingSeries = insertSyntheticIfNeeded(workingSeries, t.entry_date);
    workingSeries = insertSyntheticIfNeeded(workingSeries, t.exit_date);

    if (workingSeries.length !== beforeInsertLen) {
        headerEl.textContent = 'Note: entry/exit dates include non-trading days; chart inserts synthetic bars so the labels match the trade dates.';
    } else {
        headerEl.textContent = '';
    }

    const labels = workingSeries.map(d => d.date);
    const parseNum = (v) => {
        if (v === null || v === undefined) return NaN;
        const s = String(v).replace(/,/g, '');
        const n = parseFloat(s);
        return Number.isFinite(n) ? n : NaN;
    };
    const pickClose = (d) => {
        if (!d || typeof d !== 'object') return NaN;
        if (d.close !== undefined) return parseNum(d.close);
        if (d.rate !== undefined) return parseNum(d.rate);
        if (d.open !== undefined) return parseNum(d.open);
        if (d.high !== undefined) return parseNum(d.high);
        if (d.low !== undefined) return parseNum(d.low);
        return NaN;
    };
    const closeValues = workingSeries.map(d => {
        const v = pickClose(d);
        return Number.isFinite(v) ? v : null;
    });

    const nextType = 'line';

    const entryPrice = parseNum(t.entry_price);
    const exitPrice = parseNum(t.exit_price);
    const entrySeries = new Array(labels.length).fill(null);
    const exitSeries = new Array(labels.length).fill(null);
    const entryLabelIndex = labels.indexOf(t.entry_date);
    const exitLabelIndex = labels.indexOf(t.exit_date);
    if (entryLabelIndex >= 0 && Number.isFinite(entryPrice)) entrySeries[entryLabelIndex] = entryPrice;
    if (exitLabelIndex >= 0 && Number.isFinite(exitPrice)) exitSeries[exitLabelIndex] = exitPrice;

    if (btTradeChart) {
        btTradeChart.destroy();
        btTradeChart = null;
    }

    const ctx = canvas.getContext('2d');

    // Always render a close-price line so users can see the whole series.
    const datasets = [];

    datasets.push({
        type: 'line',
        label: 'Close',
        data: closeValues,
        borderColor: '#60a5fa',
        borderWidth: 2,
        backgroundColor: 'rgba(96,165,250,0.12)',
        fill: true,
        tension: 0.2,
        pointRadius: 0,
        spanGaps: true,
    });

    datasets.push({
        type: 'line',
        label: 'Entry',
        data: entrySeries,
        borderColor: '#22c55e',
        backgroundColor: '#22c55e',
        pointRadius: 6,
        pointHoverRadius: 7,
        showLine: false,
        spanGaps: true,
    });

    datasets.push({
        type: 'line',
        label: 'Exit',
        data: exitSeries,
        borderColor: '#f97316',
        backgroundColor: '#f97316',
        pointRadius: 6,
        pointHoverRadius: 7,
        showLine: false,
        spanGaps: true,
    });

    btTradeChart = new Chart(ctx, {
        type: nextType,
        data: {
            labels,
            datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, labels: { color: '#cbd5e1' } },
                tooltip: { enabled: true },
            },
            scales: {
                x: { type: 'category', ticks: { color: '#94a3b8', maxTicksLimit: 12 }, grid: { color: 'rgba(148,163,184,0.15)' } },
                y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.15)' } },
            }
        }
    });
}

async function fetchHistoricalData() {
    const chartContainer = document.getElementById('priceChart');
    const emptyState = document.getElementById('chartEmpty');
    
    if (chartContainer) chartContainer.style.display = 'none';
    if (emptyState) emptyState.innerHTML = '<div class="loading" style="text-align:center; padding:20px;">Loading chart data...</div>';
    if (emptyState) emptyState.style.display = 'block';
    
    try {
        const encodedPair = encodeURIComponent(selectedPair);
        const days = getTimeframeDays();
        
        if (!selectedPair || days <= 0) {
            showChartError('Invalid pair or timeframe selected');
            return;
        }
        
        const data = await fetchAPI(`/api/historical/${encodedPair}/${days}`);
        
        if (!data) {
            showChartError('Failed to fetch historical data');
            return;
        }
        
        if (!Array.isArray(data)) {
            showChartError('Invalid data format received');
            return;
        }
        
        if (data.length === 0) {
            showChartError('No historical data available for selected timeframe');
            return;
        }
        
        const validData = data.filter(item => 
            item && typeof item === 'object' && 
            item.date && item.rate && 
            !isNaN(parseFloat(item.rate))
        );
        
        if (validData.length === 0) {
            showChartError('No valid data points in historical data');
            return;
        }
        
        if (chartContainer) chartContainer.style.display = 'block';
        if (emptyState) emptyState.style.display = 'none';
        updateChart(validData);
    } catch (error) {
        console.error('Historical data fetch error:', error);
        showChartError('Error loading chart data: ' + error.message);
    }
}

function showChartError(message) {
    const emptyState = document.getElementById('chartEmpty');
    const chartContainer = document.getElementById('priceChart');
    
    if (chartContainer) chartContainer.style.display = 'none';
    if (emptyState) {
        emptyState.innerHTML = '<div class="loading" style="color: #ef4444; text-align:center; padding:20px;">' + message + '</div>';
        emptyState.style.display = 'block';
    }
    
    if (chart) {
        chart.destroy();
        chart = null;
    }
}

function updateChart(data) {
    if (!data || !Array.isArray(data) || data.length === 0) {
        showChartError('No data available to display');
        return;
    }
    
    const validPoints = data.filter(point => {
        return point && 
               typeof point === 'object' &&
               point.date && 
               point.rate && 
               !isNaN(parseFloat(point.rate));
    });
    
    if (validPoints.length === 0) {
        showChartError('No valid data points to display');
        return;
    }
    
    const ctx = document.getElementById('priceChart').getContext('2d');
    const emptyState = document.getElementById('chartEmpty');
    if (emptyState) emptyState.style.display = 'none';
    
    if (chart) {
        chart.destroy();
        chart = null;
    }
    
    try {
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: validPoints.map(d => d.date),
                datasets: [{
                    label: selectedPair + ' - ' + getTimeframeLabel(),
                    data: validPoints.map(d => parseFloat(d.rate)),
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
    } catch (error) {
        console.error('Chart rendering error:', error);
        showChartError('Error rendering chart: ' + error.message);
    }
}

function getTimeframeLabel() {
    if (timeframeUnit === 'weeks') {
        return timeframeValue + ' weeks';
    }
    if (timeframeUnit === 'months') {
        return timeframeValue + ' months';
    }
    return timeframeValue + ' days';
}

function initTimeframeControls() {
    const unitSelect = document.getElementById('timeframeUnit');
    const valueSelect = document.getElementById('timeframeValue');
    if (!unitSelect || !valueSelect) return;

    unitSelect.value = timeframeUnit;
    renderTimeframeOptions(timeframeUnit);
    valueSelect.value = String(timeframeValue);
}

function renderTimeframeOptions(unit) {
    const valueSelect = document.getElementById('timeframeValue');
    if (!valueSelect) return;

    let options = [];
    if (unit === 'days') {
        options = [7, 14, 30, 60, 90, 180, 365];
    } else if (unit === 'weeks') {
        options = [4, 8, 12, 24, 52];
    } else if (unit === 'months') {
        options = [1, 3, 6, 12, 24];
    }

    valueSelect.innerHTML = options
        .map(value => `<option value="${value}">${value}</option>`)
        .join('');

    if (!options.includes(timeframeValue)) {
        timeframeValue = options[0];
    }
    valueSelect.value = String(timeframeValue);
}

function changeTimeframeUnit() {
    const unitSelect = document.getElementById('timeframeUnit');
    if (!unitSelect) return;
    timeframeUnit = unitSelect.value;
    renderTimeframeOptions(timeframeUnit);
    fetchHistoricalData();
}

function changeTimeframeValue() {
    const valueSelect = document.getElementById('timeframeValue');
    if (!valueSelect) return;
    timeframeValue = Number(valueSelect.value);
    fetchHistoricalData();
}

function getTimeframeDays() {
    if (timeframeUnit === 'weeks') {
        return timeframeValue * 7;
    }
    if (timeframeUnit === 'months') {
        return timeframeValue * 30;
    }
    return timeframeValue;
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
    const conditions = await fetchAPI('/api/alerts/conditions');
    if (preferences && conditions) {
        btConditions = conditions;
        renderAlertPreferences(preferences, conditions);
        // Backtest uses conditions for rule configuration
        initBacktestControls();
    }
}

function renderAlertPreferences(preferences, conditions) {
    const container = document.getElementById('alertPreferencesContainer');
    
    const pairs = Object.keys(preferences).sort();
    container.innerHTML = pairs.map(pair => {
        const pref = preferences[pair];
        const alertType = pref.alert_type || 'percentage_change';
        
        let parametersHTML = '';
        if (conditions[alertType]) {
            const params = conditions[alertType].parameters;
            parametersHTML = Object.entries(params).map(([paramName, paramConfig]) => {
                let inputHTML = '';
                
                if (paramConfig.type === 'number') {
                    inputHTML = `<input type="number" 
                        id="param-${pair}-${paramName}" 
                        min="${paramConfig.min || 0}" 
                        max="${paramConfig.max || 100}" 
                        step="0.1"
                        value="${pref[paramName] !== undefined && pref[paramName] !== null ? pref[paramName] : paramConfig.default}"
                        placeholder="Default: ${paramConfig.default}">`;
                } else if (paramConfig.type === 'select') {
                    inputHTML = `<select id="param-${pair}-${paramName}" style="width: 100%; padding: 8px; background: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #f1f5f9;">
                        ${paramConfig.options.map(opt => `<option value="${opt}" ${pref[paramName] === opt ? 'selected' : ''}>${opt}</option>`).join('')}
                    </select>`;
                } else if (paramConfig.type === 'boolean') {
                    inputHTML = `<label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="param-${pair}-${paramName}" ${pref[paramName] ? 'checked' : ''} style="width: auto;">
                        <span>${paramName.replace(/_/g, ' ')}</span>
                    </label>`;
                }
                
                return `
                    <div class="form-group" style="margin-bottom: 12px;">
                        <label style="margin-bottom: 4px; font-size: 13px;">${paramName.replace(/_/g, ' ')} ${paramConfig.unit ? '(' + paramConfig.unit + ')' : ''}</label>
                        ${inputHTML}
                    </div>
                `;
            }).join('');
        }
        
        return `
            <div class="pref-item" style="border-left: 4px solid #3b82f6; padding: 16px; background: #0f172a; border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div class="form-group" style="flex: 1; margin: 0;">
                        <label style="margin-bottom: 4px; font-weight: 600;">Pair</label>
                        <input type="text" value="${pair}" disabled style="background: #1e293b; font-weight: 600;">
                    </div>
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; margin-left: 12px;">
                        <input type="checkbox" id="enabled-${pair}" ${pref.enabled ? 'checked' : ''} style="width: auto;">
                        <span style="white-space: nowrap;">Enabled</span>
                    </label>
                </div>
                
                <div class="form-group">
                    <label style="margin-bottom: 4px; font-weight: 600;">Alert Type</label>
                    <select id="type-${pair}" onchange="updateAlertTypeParameters('${pair}')" style="width: 100%; padding: 12px; background: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #f1f5f9;">
                        ${Object.entries(conditions).map(([typeKey, typeConfig]) => 
                            `<option value="${typeKey}" ${alertType === typeKey ? 'selected' : ''}>${typeConfig.name}</option>`
                        ).join('')}
                    </select>
                    <p style="font-size: 12px; color: #94a3b8; margin-top: 4px;">${conditions[alertType]?.description || ''}</p>
                </div>
                
                <div id="params-${pair}" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #334155;">
                    ${parametersHTML}
                </div>
                
                <button class="btn-success" style="width: 100%; margin-top: 12px; padding: 10px 16px;" 
                        onclick="saveAlertPreference('${pair}')">Save Alert Configuration</button>
            </div>
        `;
    }).join('');
}

async function updateAlertTypeParameters(pair) {
    const newType = document.getElementById(`type-${pair}`).value;
    const conditions = await fetchAPI('/api/alerts/conditions');
    if (!conditions) return;
    const params = conditions[newType]?.parameters || {};
    
    let parametersHTML = '';
    if (params) {
        parametersHTML = Object.entries(params).map(([paramName, paramConfig]) => {
            let inputHTML = '';
            
            if (paramConfig.type === 'number') {
                inputHTML = `<input type="number" 
                    id="param-${pair}-${paramName}" 
                    min="${paramConfig.min || 0}" 
                    max="${paramConfig.max || 100}" 
                    step="0.1"
                    value="${paramConfig.default}"
                    placeholder="Default: ${paramConfig.default}">`;
            } else if (paramConfig.type === 'select') {
                inputHTML = `<select id="param-${pair}-${paramName}" style="width: 100%; padding: 8px; background: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #f1f5f9;">
                    ${paramConfig.options.map(opt => `<option value="${opt}" ${opt === paramConfig.default ? 'selected' : ''}>${opt}</option>`).join('')}
                </select>`;
            } else if (paramConfig.type === 'boolean') {
                inputHTML = `<label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                    <input type="checkbox" id="param-${pair}-${paramName}" ${paramConfig.default ? 'checked' : ''} style="width: auto;">
                    <span>${paramName.replace(/_/g, ' ')}</span>
                </label>`;
            }
            
            return `
                <div class="form-group" style="margin-bottom: 12px;">
                    <label style="margin-bottom: 4px; font-size: 13px;">${paramName.replace(/_/g, ' ')} ${paramConfig.unit ? '(' + paramConfig.unit + ')' : ''}</label>
                    ${inputHTML}
                </div>
            `;
        }).join('');
    }
    
    document.getElementById(`params-${pair}`).innerHTML = parametersHTML;
}

async function saveAlertPreference(pair) {
    const alertType = document.getElementById(`type-${pair}`).value;
    const enabled = document.getElementById(`enabled-${pair}`).checked;
    
    const data = {
        pair: pair,
        enabled: enabled,
        alert_type: alertType
    };
    
    const conditions = await fetchAPI('/api/alerts/conditions');
    if (!conditions) return;
    const params = conditions[alertType]?.parameters || {};
    
    Object.keys(params).forEach(paramName => {
        const inputElement = document.getElementById(`param-${pair}-${paramName}`);
        if (inputElement) {
            if (params[paramName].type === 'boolean') {
                data[paramName] = inputElement.checked;
            } else if (params[paramName].type === 'number') {
                const value = parseFloat(inputElement.value);
                data[paramName] = isNaN(value) ? null : value;
            } else {
                data[paramName] = inputElement.value || null;
            }
        }
    });
    
    const result = await fetchAPI('/api/alerts/preferences', {
        method: 'POST',
        body: JSON.stringify(data)
    });
    
    if (result && result.success) {
        showToast(`Alert configuration saved for ${pair}!`, 'success');
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
