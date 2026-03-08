// Trade Page (Risk Management)
// Computes ATR(14) and daily sigma from OHLC history.

let _tradeLast = {
    pair: null,
    close: null,
    atr: null,
    sigma: null,
};

let _tradeLastSizing = {
    equity: null,
    riskPct: null,
    riskUsd: null,
    quantity: null,
    notional: null,
    stopDistance: null,
    stopLong: null,
    stopShort: null,
};

let _tradeDiaryEntries = new Map();
let _tradeDiaryModalState = {
    mode: 'create',
    tradeId: null,
};

function _setTradeStatus(message, isError = false) {
    const el = document.getElementById('tradeStatus');
    if (!el) return;
    el.style.display = 'block';
    el.style.color = isError ? '#fca5a5' : '#94a3b8';
    el.textContent = message;
}

function _hideTradeStatus() {
    const el = document.getElementById('tradeStatus');
    if (!el) return;
    el.style.display = 'none';
    el.textContent = '';
}

function _setTradeMetricsVisible(visible) {
    const el = document.getElementById('tradeMetrics');
    if (!el) return;
    el.style.display = visible ? 'block' : 'none';
}

function _setTradeDiaryStatus(message, isError = false) {
    const el = document.getElementById('tradeDiaryStatus');
    if (!el) return;
    if (!message) {
        el.style.display = 'none';
        el.textContent = '';
        return;
    }
    el.style.display = 'block';
    el.style.color = isError ? '#fca5a5' : '#94a3b8';
    el.textContent = message;
}

function _setTradeDiaryModalStatus(message, isError = false) {
    const el = document.getElementById('tradeDiaryModalStatus');
    if (!el) return;
    if (!message) {
        el.style.display = 'none';
        el.textContent = '';
        return;
    }
    el.style.display = 'block';
    el.style.color = isError ? '#fca5a5' : '#94a3b8';
    el.textContent = message;
}

function _safeNumber(x) {
    const v = Number(x);
    return Number.isFinite(v) ? v : null;
}

function _escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function _formatUsd(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return '—';
    return `$${num.toFixed(2)}`;
}

function _formatSignedUsd(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return '—';
    return `${num >= 0 ? '+' : '-'}$${Math.abs(num).toFixed(2)}`;
}

function _currentTradePlannedRisk() {
    const backdrop = document.getElementById('tradeDiaryModalBackdrop');
    if (!backdrop || backdrop.style.display === 'none') return 0;

    const entryPrice = _safeNumber(document.getElementById('tradeDiaryEntryPrice')?.value);
    const stopPrice = _safeNumber(document.getElementById('tradeDiaryStopPrice')?.value);
    const quantity = _safeNumber(document.getElementById('tradeDiaryQuantity')?.value);
    if (entryPrice == null || stopPrice == null || quantity == null || quantity <= 0) return 0;
    const newRisk = Math.abs(entryPrice - stopPrice) * quantity;

    if (_tradeDiaryModalState.mode === 'edit' && _tradeDiaryModalState.tradeId != null) {
        const current = _tradeDiaryEntries.get(Number(_tradeDiaryModalState.tradeId));
        const existingRisk = Number(current?.risk_amount_usd || 0);
        return newRisk - existingRisk;
    }

    if (_tradeDiaryModalState.mode === 'close') {
        return 0;
    }

    return newRisk;
}

function _populateTradeDiaryAssetOptions(selectedValue) {
    const el = document.getElementById('tradeDiaryAsset');
    if (!el) return;
    const options = getAvailablePairs();
    const prev = selectedValue || el.value || String(document.getElementById('tradeAsset')?.value || window.selectedPair || 'GOLD/USD');
    el.innerHTML = '';
    for (const pair of options) {
        const opt = document.createElement('option');
        opt.value = pair;
        opt.textContent = pair;
        el.appendChild(opt);
    }
    if ([...el.options].some(o => o.value === prev)) {
        el.value = prev;
    }
}

function _getTradeDiaryEntryById(tradeId) {
    return _tradeDiaryEntries.get(Number(tradeId)) || null;
}

function _setTradeDiaryFieldsDisabled(disabled) {
    const ids = ['tradeDiaryAsset', 'tradeDiarySide', 'tradeDiaryEntryPrice', 'tradeDiaryStopPrice', 'tradeDiaryQuantity', 'tradeDiaryEntryReason', 'tradeDiaryNotes'];
    for (const id of ids) {
        const el = document.getElementById(id);
        if (el) el.disabled = disabled;
    }
    const fillBtn = document.getElementById('tradeDiaryModalFillBtn');
    if (fillBtn) fillBtn.style.display = disabled ? 'none' : 'inline-flex';
}

function closeTradeDiaryModal() {
    const backdrop = document.getElementById('tradeDiaryModalBackdrop');
    if (!backdrop) return;
    backdrop.style.display = 'none';
    _tradeDiaryModalState = { mode: 'create', tradeId: null };
    _setTradeDiaryModalStatus('');
    refreshTradeRiskSummary();
}

function handleTradeDiaryModalBackdrop(event) {
    if (event.target?.id === 'tradeDiaryModalBackdrop') {
        closeTradeDiaryModal();
    }
}

function openTradeDiaryModal(mode = 'create', tradeId = null, useLatestSizing = false) {
    const backdrop = document.getElementById('tradeDiaryModalBackdrop');
    if (!backdrop) return;

    _tradeDiaryModalState = { mode, tradeId };
    _populateTradeDiaryAssetOptions();
    _setTradeDiaryModalStatus('');

    const titleEl = document.getElementById('tradeDiaryModalTitle');
    const subtitleEl = document.getElementById('tradeDiaryModalSubtitle');
    const contextEl = document.getElementById('tradeDiaryModalContext');
    const closeFieldsEl = document.getElementById('tradeDiaryModalCloseFields');
    const saveBtn = document.getElementById('tradeDiaryModalSaveBtn');
    const closePriceEl = document.getElementById('tradeDiaryClosePrice');
    const closeReasonEl = document.getElementById('tradeDiaryCloseReason');
    const entryReasonEl = document.getElementById('tradeDiaryEntryReason');
    const notesEl = document.getElementById('tradeDiaryNotes');
    const sideEl = document.getElementById('tradeDiarySide');
    const assetEl = document.getElementById('tradeDiaryAsset');
    const entryPriceEl = document.getElementById('tradeDiaryEntryPrice');
    const stopPriceEl = document.getElementById('tradeDiaryStopPrice');
    const quantityEl = document.getElementById('tradeDiaryQuantity');

    if (!titleEl || !subtitleEl || !contextEl || !closeFieldsEl || !saveBtn || !assetEl || !sideEl || !entryPriceEl || !stopPriceEl || !quantityEl || !entryReasonEl || !notesEl || !closePriceEl || !closeReasonEl) {
        return;
    }

    contextEl.style.display = 'none';
    contextEl.innerHTML = '';
    closeFieldsEl.style.display = 'none';

    if (mode === 'create') {
        titleEl.textContent = 'New Trade Diary Entry';
        subtitleEl.textContent = 'Capture the trade plan, size, and reason before you execute.';
        saveBtn.textContent = 'Log Trade';
        _setTradeDiaryFieldsDisabled(false);

        assetEl.value = String(document.getElementById('tradeAsset')?.value || window.selectedPair || assetEl.value || 'GOLD/USD');
        sideEl.value = 'long';
        closePriceEl.value = '';
        closeReasonEl.value = '';
        entryReasonEl.value = '';
        notesEl.value = '';
        entryPriceEl.value = _tradeLast.close != null ? _tradeLast.close.toFixed(4) : '';
        stopPriceEl.value = '';
        quantityEl.value = '';

        if (useLatestSizing && _tradeLastSizing.quantity != null) {
            applyTradeSizingToDiary(true);
        }
    } else {
        const entry = _getTradeDiaryEntryById(tradeId);
        if (!entry) {
            _setTradeDiaryStatus('Trade diary entry not found.', true);
            return;
        }

        assetEl.value = String(entry.pair || assetEl.value || 'GOLD/USD');
        sideEl.value = String(entry.side || 'long');
        entryPriceEl.value = entry.entry_price != null ? Number(entry.entry_price).toFixed(4) : '';
        stopPriceEl.value = entry.stop_price != null ? Number(entry.stop_price).toFixed(4) : '';
        quantityEl.value = entry.quantity != null ? Number(entry.quantity).toFixed(4) : '';
        entryReasonEl.value = String(entry.entry_reason || '');
        notesEl.value = String(entry.notes || '');
        closePriceEl.value = entry.close_price != null ? Number(entry.close_price).toFixed(4) : '';
        closeReasonEl.value = String(entry.close_reason || '');

        if (mode === 'edit') {
            titleEl.textContent = 'Edit Trade Diary Entry';
            subtitleEl.textContent = 'Adjust the journal details without editing inline on the page.';
            saveBtn.textContent = 'Save Changes';
            _setTradeDiaryFieldsDisabled(false);
            closeFieldsEl.style.display = String(entry.status || '') === 'closed' ? 'grid' : 'none';
            contextEl.style.display = 'block';
            contextEl.innerHTML = `Status: ${_escapeHtml(String(entry.status || '').toUpperCase())} · Risk ${_formatUsd(entry.risk_amount_usd)}${entry.realized_pnl != null ? ` · Realized P/L ${_formatSignedUsd(entry.realized_pnl)}` : ''}`;
        } else if (mode === 'close') {
            titleEl.textContent = 'Close Trade';
            subtitleEl.textContent = 'Record the exit price and why you are closing the position.';
            saveBtn.textContent = 'Close Trade';
            _setTradeDiaryFieldsDisabled(true);
            closeFieldsEl.style.display = 'grid';
            contextEl.style.display = 'block';
            contextEl.innerHTML = `${_escapeHtml(entry.pair)} · ${_escapeHtml(String(entry.side || '').toUpperCase())} · Entry ${entry.entry_price != null ? Number(entry.entry_price).toFixed(4) : '—'} · Stop ${entry.stop_price != null ? Number(entry.stop_price).toFixed(4) : '—'} · Risk ${_formatUsd(entry.risk_amount_usd)}`;
        }
    }

    backdrop.style.display = 'flex';
    refreshTradeRiskSummary();
}

function _renderTradeRiskSummary(summary) {
    const el = document.getElementById('tradeRiskSummary');
    if (!el) return;
    if (!summary) {
        el.innerHTML = '';
        return;
    }

    const remainingClass = (summary.projected_remaining_risk_usd ?? 0) < 0 ? '#fca5a5' : '#cbd5e1';
    const allowedText = summary.can_open_new_trade ? 'Within daily budget' : 'Projected trade exceeds daily budget';
    const allowedColor = summary.can_open_new_trade ? '#86efac' : '#fca5a5';

    el.innerHTML = `
        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 12px;">
            <div class="card" style="margin:0;">
                <h3 style="margin:0 0 6px 0;">Daily Limit</h3>
                <div style="color:#cbd5e1; font-size: 14px;">${_formatUsd(summary.daily_limit_usd)}</div>
                <div style="color:#94a3b8; font-size: 12px; margin-top:4px;">${Number(summary.daily_limit_pct || 0).toFixed(2)}% of current equity</div>
            </div>
            <div class="card" style="margin:0;">
                <h3 style="margin:0 0 6px 0;">Opened Today</h3>
                <div style="color:#cbd5e1; font-size: 14px;">${_formatUsd(summary.opened_today_risk_usd)}</div>
                <div style="color:#94a3b8; font-size: 12px; margin-top:4px;">${summary.today_trade_count || 0} trades logged today</div>
            </div>
            <div class="card" style="margin:0;">
                <h3 style="margin:0 0 6px 0;">Active Risk</h3>
                <div style="color:#cbd5e1; font-size: 14px;">${_formatUsd(summary.active_risk_usd)}</div>
                <div style="color:#94a3b8; font-size: 12px; margin-top:4px;">${summary.open_trade_count || 0} open trades</div>
            </div>
            <div class="card" style="margin:0;">
                <h3 style="margin:0 0 6px 0;">Remaining Today</h3>
                <div style="color:${remainingClass}; font-size: 14px;">${_formatUsd(summary.remaining_risk_usd)}</div>
                <div style="color:${allowedColor}; font-size: 12px; margin-top:4px;">After this trade: ${_formatUsd(summary.projected_remaining_risk_usd)} · ${allowedText}</div>
            </div>
        </div>
    `;
}

async function refreshTradeRiskSummary() {
    const equity = _safeNumber(document.getElementById('tradeEquity')?.value) || 0;
    const plannedRisk = _currentTradePlannedRisk();
    const summary = await fetchAPI(`/api/trade/summary?equity=${encodeURIComponent(equity)}&planned_risk_usd=${encodeURIComponent(plannedRisk)}`);
    if (summary) {
        _renderTradeRiskSummary(summary);
    }
}

async function loadTradeRiskSettings() {
    const settings = await fetchAPI('/api/settings');
    if (!settings) return;
    const el = document.getElementById('tradeDailyRiskLimitPct');
    if (el && settings.daily_risk_limit_pct !== undefined) {
        el.value = settings.daily_risk_limit_pct;
    }
}

async function saveTradeRiskLimit() {
    const dailyRiskLimitPct = _safeNumber(document.getElementById('tradeDailyRiskLimitPct')?.value);
    if (dailyRiskLimitPct == null || dailyRiskLimitPct <= 0) {
        _setTradeDiaryStatus('Enter a valid daily risk limit (%).', true);
        return;
    }

    const result = await fetchAPI('/api/settings', {
        method: 'POST',
        body: JSON.stringify({ daily_risk_limit_pct: dailyRiskLimitPct })
    });

    if (result && result.success) {
        _setTradeDiaryStatus('Daily risk limit saved.');
        await refreshTradeRiskSummary();
    }
}

function _stddev(arr) {
    const xs = (arr || []).filter(v => Number.isFinite(v));
    if (xs.length < 2) return null;
    const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
    const varSum = xs.reduce((a, b) => a + (b - mean) ** 2, 0);
    return Math.sqrt(varSum / (xs.length - 1));
}

function _computeSigmaDailyPct(closes, windowDays = 252) {
    // daily close-to-close log return sigma over the last N days
    if (!Array.isArray(closes) || closes.length < windowDays + 1) return null;
    const rets = [];
    for (let i = 1; i < closes.length; i++) {
        const c0 = closes[i - 1];
        const c1 = closes[i];
        if (!Number.isFinite(c0) || !Number.isFinite(c1) || c0 <= 0 || c1 <= 0) continue;
        rets.push(Math.log(c1 / c0));
    }
    const tail = rets.slice(Math.max(0, rets.length - windowDays));
    const sd = _stddev(tail);
    return sd == null ? null : sd * 100.0;
}

function _computeAtrWilder(ohlc, windowDays = 14) {
    if (!Array.isArray(ohlc) || ohlc.length < windowDays + 1) return null;

    const highs = [];
    const lows = [];
    const closes = [];
    for (const r of ohlc) {
        highs.push(_safeNumber(r.high));
        lows.push(_safeNumber(r.low));
        closes.push(_safeNumber(r.close));
    }

    const tr = [];
    for (let i = 0; i < ohlc.length; i++) {
        const h = highs[i];
        const l = lows[i];
        const cPrev = i > 0 ? closes[i - 1] : null;
        if (!Number.isFinite(h) || !Number.isFinite(l)) {
            tr.push(null);
            continue;
        }
        const a = h - l;
        const b = (cPrev != null && Number.isFinite(cPrev)) ? Math.abs(h - cPrev) : a;
        const c = (cPrev != null && Number.isFinite(cPrev)) ? Math.abs(l - cPrev) : a;
        tr.push(Math.max(a, b, c));
    }

    // Seed ATR with SMA of first N valid TR values starting at index 1 (needs prev close)
    const seedStart = 1;
    const seedEnd = seedStart + windowDays; // exclusive
    if (ohlc.length < seedEnd) return null;

    let sum = 0;
    for (let i = seedStart; i < seedEnd; i++) {
        const x = tr[i];
        if (!Number.isFinite(x)) return null;
        sum += x;
    }
    let atr = sum / windowDays;

    // Wilder smoothing
    for (let i = seedEnd; i < tr.length; i++) {
        const x = tr[i];
        if (!Number.isFinite(x)) continue;
        atr = (atr * (windowDays - 1) + x) / windowDays;
    }

    return atr;
}

async function initTradePage() {
    try {
        const sel = document.getElementById('tradeAsset');
        if (!sel) return;

        const alreadyInit = (window._tradeInitialized === true);

        // Preserve the user's current selection across refreshes.
        const prev = String(sel.value || '').trim();

        // Populate from liveRates if available; fall back to a safe default.
        const options = getAvailablePairs();

        // Avoid rebuilding DOM if the option set didn't change.
        const optionsKey = options.join('||');
        const prevOptionsKey = String(sel.dataset.optionsKey || '');
        const needsRebuild = (optionsKey !== prevOptionsKey) || (sel.options.length !== options.length);

        if (needsRebuild) {
            sel.innerHTML = '';
            for (const p of options) {
                const opt = document.createElement('option');
                opt.value = p;
                opt.textContent = p;
                sel.appendChild(opt);
            }
            sel.dataset.optionsKey = optionsKey;
        }

        // Keep previous selection when possible; otherwise default to selectedPair.
        if (prev && [...sel.options].some(o => o.value === prev)) {
            sel.value = prev;
        } else {
            const cur = String(window.selectedPair || 'GOLD/USD');
            if ([...sel.options].some(o => o.value === cur)) {
                sel.value = cur;
            }
        }

        // Only reset visuals on first init. On refreshes, preserve computed metrics.
        if (!alreadyInit) {
            _setTradeMetricsVisible(false);
            _hideTradeStatus();
            _setTradeDiaryStatus('');

            const refreshFields = ['tradeEquity', 'tradeDiaryEntryPrice', 'tradeDiaryStopPrice', 'tradeDiaryQuantity'];
            for (const id of refreshFields) {
                const el = document.getElementById(id);
                if (el) {
                    el.addEventListener('change', () => { refreshTradeRiskSummary(); });
                    el.addEventListener('input', () => { refreshTradeRiskSummary(); });
                }
            }

            const tradeDiarySide = document.getElementById('tradeDiarySide');
            if (tradeDiarySide) {
                tradeDiarySide.addEventListener('change', () => { refreshTradeRiskSummary(); });
            }

            document.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') {
                    closeTradeDiaryModal();
                }
            });
        }

        window._tradeInitialized = true;

        const page = document.getElementById('trade');
        const isVisible = page && page.classList.contains('active');
        if (!alreadyInit || isVisible) {
            await loadTradeRiskSettings();
            await refreshTradeRiskSummary();
            await loadTradeDiary();
        }
    } catch (_) {
        // ignore
    }
}

function tradeUseSelectedPair() {
    const sel = document.getElementById('tradeAsset');
    if (!sel) return;
    const cur = String(window.selectedPair || 'GOLD/USD');
    sel.value = cur;
}

async function loadTradeMetrics() {
    const sel = document.getElementById('tradeAsset');
    const daysEl = document.getElementById('tradeDays');
    if (!sel) return;

    const pair = String(sel.value || '').trim();
    const days = Math.max(300, Math.min(5000, parseInt(String(daysEl?.value || '800'), 10) || 800));

    _setTradeMetricsVisible(false);
    _setTradeStatus(`Loading OHLC for ${pair} (${days}d)...`);

    const endpoint = `/api/historical-ohlc/${encodeURIComponent(pair)}/${days}`;
    const data = await fetchAPI(endpoint);

    if (!data) {
        _setTradeStatus('Failed to load OHLC (no response).', true);
        return;
    }

    // Need >= 253 daily bars to compute 252-trading-day sigma.
    if (!Array.isArray(data) || data.length < 253) {
        _setTradeStatus('Not enough OHLC history returned (need ~1y of daily bars for σ(252)). Increase History Window days.', true);
        return;
    }

    // Normalize / sort
    const rows = data
        .filter(r => r && r.date && r.close != null)
        .map(r => ({
            date: String(r.date),
            open: _safeNumber(r.open),
            high: _safeNumber(r.high),
            low: _safeNumber(r.low),
            close: _safeNumber(r.close),
        }))
        .filter(r => r.close != null)
        .sort((a, b) => a.date.localeCompare(b.date));

    const closes = rows.map(r => r.close).filter(v => v != null);
    const lastClose = closes.length ? closes[closes.length - 1] : null;

    const atr = _computeAtrWilder(rows, 14);
    const sigma = _computeSigmaDailyPct(closes, 252);

    if (lastClose == null || atr == null || sigma == null) {
        _setTradeStatus('Failed to compute metrics (missing OHLC).', true);
        return;
    }

    _tradeLast = { pair, close: lastClose, atr, sigma };

    document.getElementById('tradeAtr').textContent = `${atr.toFixed(2)} (ATR%) ${(atr / lastClose * 100).toFixed(2)}%`;
    document.getElementById('tradeSigma').textContent = `${sigma.toFixed(4)}% (daily log-return σ)`;
    document.getElementById('tradeClose').textContent = `${lastClose.toFixed(4)}`;

    document.getElementById('tradeSizing').textContent = '';

    _hideTradeStatus();
    _setTradeMetricsVisible(true);
}

function computePositionSizing() {
    const equity = _safeNumber(document.getElementById('tradeEquity')?.value);
    const riskPct = _safeNumber(document.getElementById('tradeRiskPct')?.value);
    const atrMult = _safeNumber(document.getElementById('tradeAtrMult')?.value);

    const outEl = document.getElementById('tradeSizing');
    if (!outEl) return;

    if (_tradeLast.close == null || _tradeLast.atr == null) {
        outEl.textContent = 'Compute metrics first.';
        return;
    }

    if (equity == null || riskPct == null || atrMult == null || equity <= 0 || riskPct <= 0 || atrMult <= 0) {
        outEl.textContent = 'Enter valid equity, risk %, and ATR multiple.';
        return;
    }

    const riskUsd = equity * (riskPct / 100.0);
    const stopDistance = _tradeLast.atr * atrMult;
    if (!(stopDistance > 0)) {
        outEl.textContent = 'Stop distance is invalid.';
        return;
    }

    const qty = riskUsd / stopDistance;
    const notional = qty * _tradeLast.close;
    const stopLong = _tradeLast.close - stopDistance;
    const stopShort = _tradeLast.close + stopDistance;

    _tradeLastSizing = {
        equity,
        riskPct,
        riskUsd,
        quantity: qty,
        notional,
        stopDistance,
        stopLong,
        stopShort,
    };

    outEl.textContent = `Risk $${riskUsd.toFixed(2)}; Stop distance ${stopDistance.toFixed(4)}. ` +
        `Position size ≈ ${qty.toFixed(4)} units (notional ≈ $${notional.toFixed(2)}). ` +
        `Suggested stops: long ${stopLong.toFixed(4)}, short ${stopShort.toFixed(4)}.`;

    applyTradeSizingToDiary(true);
    refreshTradeRiskSummary();
}

function applyTradeSizingToDiary(silent = false) {
    if (_tradeLast.close == null || _tradeLastSizing.quantity == null) {
        if (!silent) {
            _setTradeDiaryStatus('Compute position sizing first.', true);
        }
        return;
    }

    const side = String(document.getElementById('tradeDiarySide')?.value || 'long');
    const entryPriceEl = document.getElementById('tradeDiaryEntryPrice');
    const stopPriceEl = document.getElementById('tradeDiaryStopPrice');
    const quantityEl = document.getElementById('tradeDiaryQuantity');
    if (!entryPriceEl || !stopPriceEl || !quantityEl) return;

    entryPriceEl.value = _tradeLast.close.toFixed(4);
    stopPriceEl.value = (side === 'short' ? _tradeLastSizing.stopShort : _tradeLastSizing.stopLong).toFixed(4);
    quantityEl.value = _tradeLastSizing.quantity.toFixed(4);

    if (!silent) {
        _setTradeDiaryStatus('Filled diary form from the latest sizing calculation.');
        _setTradeDiaryModalStatus('Filled from the latest sizing calculation.');
    }
    refreshTradeRiskSummary();
}

async function loadTradeDiary() {
    const result = await fetchAPI('/api/trade/diary?limit=40');
    const container = document.getElementById('tradeDiaryList');
    if (!container) return;
    if (!result || !result.success) {
        container.innerHTML = '<div class="loading">Failed to load trade diary</div>';
        return;
    }

    const entries = Array.isArray(result.entries) ? result.entries : [];
    _tradeDiaryEntries = new Map(entries.map(entry => [Number(entry.id), entry]));
    if (!entries.length) {
        container.innerHTML = '<div class="loading">No trade journal entries yet</div>';
        return;
    }

    container.innerHTML = entries.map(entry => {
        const isOpen = String(entry.status || '') === 'open';
        const statusColor = isOpen ? '#86efac' : '#94a3b8';
        const pnl = entry.realized_pnl == null ? '' : `<div style="font-size: 12px; color: ${entry.realized_pnl >= 0 ? '#86efac' : '#fca5a5'};">Realized P/L: ${_formatSignedUsd(entry.realized_pnl)}</div>`;
        const closeReason = entry.close_reason ? `<div style="margin-top: 10px; color:#cbd5e1; font-size: 13px; white-space: pre-wrap;"><strong>Exit:</strong> ${_escapeHtml(entry.close_reason)}</div>` : '';
        const actions = `
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top: 12px;">
                <button class="btn-secondary" style="width:auto;" onclick="openTradeDiaryModal('edit', ${entry.id})">Edit</button>
                ${isOpen ? `<button class="btn-danger" style="width:auto;" onclick="openTradeDiaryModal('close', ${entry.id})">Close</button>` : ''}
            </div>
        `;

        return `
            <div class="alert-item" style="display:block; background:#0f172a; border-left: 4px solid ${statusColor}; margin-bottom: 12px;">
                <div style="display:flex; justify-content:space-between; gap:12px; align-items:flex-start; flex-wrap:wrap;">
                    <div>
                        <div style="font-weight:600; color:#f8fafc;">${_escapeHtml(entry.pair)} · ${_escapeHtml(String(entry.side || '').toUpperCase())}</div>
                        <div style="font-size:12px; color:${statusColor}; margin-top:4px;">${_escapeHtml(String(entry.status || '').toUpperCase())}</div>
                    </div>
                    <div style="text-align:right; font-size:12px; color:#94a3b8;">
                        <div>${entry.opened_at ? new Date(entry.opened_at).toLocaleString() : '—'}</div>
                        ${entry.closed_at ? `<div>Closed: ${new Date(entry.closed_at).toLocaleString()}</div>` : ''}
                    </div>
                </div>

                <div style="display:grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-top: 10px; font-size: 12px; color:#cbd5e1;">
                    <div><strong>Entry</strong><br>${entry.entry_price != null ? Number(entry.entry_price).toFixed(4) : '—'}</div>
                    <div><strong>Stop</strong><br>${entry.stop_price != null ? Number(entry.stop_price).toFixed(4) : '—'}</div>
                    <div><strong>Qty</strong><br>${entry.quantity != null ? Number(entry.quantity).toFixed(4) : '—'}</div>
                    <div><strong>Risk</strong><br>${_formatUsd(entry.risk_amount_usd)}</div>
                    <div><strong>Risk %</strong><br>${entry.risk_pct_of_equity != null ? Number(entry.risk_pct_of_equity).toFixed(2) + '%' : '—'}</div>
                </div>

                <div style="margin-top: 10px; color:#cbd5e1; font-size: 13px; white-space: pre-wrap;"><strong>Entry:</strong> ${_escapeHtml(entry.entry_reason || '')}</div>
                ${entry.notes ? `<div style="margin-top: 8px; color:#94a3b8; font-size: 13px; white-space: pre-wrap;"><strong>Notes:</strong> ${_escapeHtml(entry.notes)}</div>` : ''}
                ${pnl}
                ${closeReason}
                ${actions}
            </div>
        `;
    }).join('');
}

async function logTradeEntry() {
    if (_tradeLast.close == null || _tradeLast.atr == null) {
        _setTradeDiaryModalStatus('Compute trade metrics before logging a trade.', true);
        return;
    }

    const payload = {
        pair: String(document.getElementById('tradeDiaryAsset')?.value || document.getElementById('tradeAsset')?.value || '').trim(),
        side: String(document.getElementById('tradeDiarySide')?.value || 'long').trim(),
        entry_price: _safeNumber(document.getElementById('tradeDiaryEntryPrice')?.value),
        stop_price: _safeNumber(document.getElementById('tradeDiaryStopPrice')?.value),
        quantity: _safeNumber(document.getElementById('tradeDiaryQuantity')?.value),
        equity: _safeNumber(document.getElementById('tradeEquity')?.value),
        entry_reason: String(document.getElementById('tradeDiaryEntryReason')?.value || '').trim(),
        notes: String(document.getElementById('tradeDiaryNotes')?.value || '').trim(),
        atr: _tradeLast.atr,
        sigma: _tradeLast.sigma,
    };

    const result = await fetchAPI('/api/trade/diary', {
        method: 'POST',
        body: JSON.stringify(payload)
    });

    if (!result || !result.success) {
        _setTradeDiaryModalStatus(result?.error || 'Failed to log trade.', true);
        if (result?.summary) {
            _renderTradeRiskSummary(result.summary);
        }
        return;
    }

    _setTradeDiaryStatus('Trade logged to diary.');
    _setTradeDiaryModalStatus('');
    closeTradeDiaryModal();
    if (result.summary) {
        _renderTradeRiskSummary(result.summary);
    } else {
        await refreshTradeRiskSummary();
    }
    await loadTradeDiary();
}

async function saveTradeDiaryEdit() {
    const tradeId = _tradeDiaryModalState.tradeId;
    const payload = {
        pair: String(document.getElementById('tradeDiaryAsset')?.value || '').trim(),
        side: String(document.getElementById('tradeDiarySide')?.value || 'long').trim(),
        entry_price: _safeNumber(document.getElementById('tradeDiaryEntryPrice')?.value),
        stop_price: _safeNumber(document.getElementById('tradeDiaryStopPrice')?.value),
        quantity: _safeNumber(document.getElementById('tradeDiaryQuantity')?.value),
        equity: _safeNumber(document.getElementById('tradeEquity')?.value),
        entry_reason: String(document.getElementById('tradeDiaryEntryReason')?.value || '').trim(),
        notes: String(document.getElementById('tradeDiaryNotes')?.value || '').trim(),
        close_price: _safeNumber(document.getElementById('tradeDiaryClosePrice')?.value),
        close_reason: String(document.getElementById('tradeDiaryCloseReason')?.value || '').trim(),
        atr: _tradeLast.atr,
        sigma: _tradeLast.sigma,
    };

    const result = await fetchAPI(`/api/trade/diary/${tradeId}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
    });

    if (!result || !result.success) {
        _setTradeDiaryModalStatus(result?.error || 'Failed to update trade.', true);
        if (result?.summary) {
            _renderTradeRiskSummary(result.summary);
        }
        return;
    }

    _setTradeDiaryStatus('Trade diary entry updated.');
    _setTradeDiaryModalStatus('');
    closeTradeDiaryModal();
    if (result.summary) {
        _renderTradeRiskSummary(result.summary);
    } else {
        await refreshTradeRiskSummary();
    }
    await loadTradeDiary();
}

async function closeTradeEntry(tradeId) {
    const closeReason = String(document.getElementById('tradeDiaryCloseReason')?.value || '').trim();
    const closePrice = _safeNumber(document.getElementById('tradeDiaryClosePrice')?.value);
    const equity = _safeNumber(document.getElementById('tradeEquity')?.value) || 0;

    if (!closeReason) {
        _setTradeDiaryModalStatus('Enter a close reason before closing the trade.', true);
        return;
    }

    const result = await fetchAPI(`/api/trade/diary/${tradeId}/close`, {
        method: 'POST',
        body: JSON.stringify({ close_reason: closeReason, close_price: closePrice, equity })
    });

    if (!result || !result.success) {
        _setTradeDiaryModalStatus(result?.error || 'Failed to close trade.', true);
        return;
    }

    _setTradeDiaryStatus('Trade closed and diary updated.');
    _setTradeDiaryModalStatus('');
    closeTradeDiaryModal();
    if (result.summary) {
        _renderTradeRiskSummary(result.summary);
    } else {
        await refreshTradeRiskSummary();
    }
    await loadTradeDiary();
}

async function saveTradeDiaryModal() {
    if (_tradeDiaryModalState.mode === 'create') {
        await logTradeEntry();
        return;
    }
    if (_tradeDiaryModalState.mode === 'edit') {
        await saveTradeDiaryEdit();
        return;
    }
    if (_tradeDiaryModalState.mode === 'close' && _tradeDiaryModalState.tradeId != null) {
        await closeTradeEntry(_tradeDiaryModalState.tradeId);
    }
}
