// Forecast Page Module
// Fetches and displays the latest DL forecast from /api/dl/forecast/latest

let dlForecastChart = null;

function _destroyDlForecastChart() {
    try {
        if (dlForecastChart) {
            dlForecastChart.destroy();
        }
    } catch (_) {
        // ignore
    }
    dlForecastChart = null;
}

function _setDlForecastStatus({ loading = false, empty = false, message = '' } = {}) {
    const statusEl = document.getElementById('dlForecastStatus');
    const emptyEl = document.getElementById('dlForecastEmpty');
    const metaEl = document.getElementById('dlForecastMeta');
    const contentEl = document.getElementById('dlForecastContent');

    if (statusEl) {
        statusEl.style.display = loading ? 'block' : 'none';
        if (loading) statusEl.textContent = message || 'Loading forecast...';
    }
    if (emptyEl) {
        emptyEl.style.display = empty ? 'block' : 'none';
        if (empty) emptyEl.textContent = message || 'No forecast data available';
    }
    if (metaEl) metaEl.textContent = '';
    if (contentEl) contentEl.style.display = 'none';
}

async function loadLatestForecast() {
    const canvas = document.getElementById('dlForecastChart');
    const metaEl = document.getElementById('dlForecastMeta');
    const contentEl = document.getElementById('dlForecastContent');
    const assetEl = document.getElementById('dlForecastAsset');

    if (!canvas) return;

    _destroyDlForecastChart();
    _setDlForecastStatus({ loading: true, message: 'Loading forecast...' });

    const asset = String(assetEl?.value || '').trim();
    const qs = asset ? `?asset=${encodeURIComponent(asset)}` : '';
    const data = await fetchAPI('/api/dl/forecast/latest' + qs);

    if (!data) {
        _setDlForecastStatus({ empty: true, message: 'Failed to load forecast.' });
        return;
    }

    if (data.success === false) {
        _setDlForecastStatus({ empty: true, message: data.error || 'Failed to load forecast.' });
        return;
    }

    const run = data.run || null;
    const series = Array.isArray(data.forecast) ? data.forecast : [];

    if (!run || series.length === 0) {
        _setDlForecastStatus({ empty: true, message: 'No forecast data available.' });
        if (contentEl) {
            contentEl.style.display = 'block';
            contentEl.textContent = JSON.stringify(data, null, 2);
        }
        return;
    }

    // Show meta
    if (metaEl) {
        const assetStr = run.asset ? ` asset=${run.asset}` : '';
        metaEl.textContent = `run_id=${run.id}${assetStr} model=${run.model_type} lookback_days=${run.lookback_days} horizon_days=${run.horizon_days} created_at=${run.created_at}`;
    }

    // Render chart
    const labels = series.map(r => r.dt);
    const values = series.map(r => r.predicted_close);

    const ctx = canvas.getContext('2d');
    dlForecastChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Predicted Close',
                    data: values,
                    borderColor: '#60a5fa',
                    backgroundColor: 'rgba(96, 165, 250, 0.10)',
                    tension: 0.15,
                    pointRadius: 0,
                    borderWidth: 2,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: {
                    labels: { color: '#cbd5e1' }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#94a3b8', maxTicksLimit: 10 },
                    grid: { color: 'rgba(148, 163, 184, 0.15)' }
                },
                y: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(148, 163, 184, 0.15)' }
                }
            }
        }
    });

    // Raw JSON
    if (contentEl) {
        contentEl.style.display = 'block';
        contentEl.textContent = JSON.stringify(data, null, 2);
    }

    _setDlForecastStatus({ loading: false, empty: false });
}

function forecastUseSelectedPair() {
    try {
        const el = document.getElementById('dlForecastAsset');
        if (!el) return;
        el.value = String(window.selectedPair || 'GOLD/USD');
    } catch (_) {
        // ignore
    }
}
