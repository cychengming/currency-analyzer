// Trade Page (Risk Management)
// Computes ATR(14) and daily sigma from OHLC history.

let _tradeLast = {
    pair: null,
    close: null,
    atr: null,
    sigma: null,
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

function _safeNumber(x) {
    const v = Number(x);
    return Number.isFinite(v) ? v : null;
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

function initTradePage() {
    try {
        const sel = document.getElementById('tradeAsset');
        if (!sel) return;

        const alreadyInit = (window._tradeInitialized === true);

        // Preserve the user's current selection across refreshes.
        const prev = String(sel.value || '').trim();

        // Populate from liveRates if available; fall back to a safe default.
        const pairs = Object.keys(window.liveRates || {}).sort();
        const defaults = ['GOLD/USD', 'SILVER/USD', 'EUR/USD', 'GBP/USD', 'AUD/USD', 'NZD/USD', 'USD/CAD', 'USD/CHF', 'USD/JPY'];
        const options = (pairs && pairs.length) ? pairs : defaults;

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
        }

        window._tradeInitialized = true;
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

    outEl.textContent = `Risk $${riskUsd.toFixed(2)}; Stop distance ${stopDistance.toFixed(4)}. ` +
        `Position size ≈ ${qty.toFixed(4)} units (notional ≈ $${notional.toFixed(2)}). ` +
        `Suggested stops: long ${stopLong.toFixed(4)}, short ${stopShort.toFixed(4)}.`;
}
