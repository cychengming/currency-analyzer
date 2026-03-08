// Deep Learning Trigger Page
// Provides controls to run ingest/train via backend endpoints.

let dlJobPollTimer = null;

function _setDlJobStatus(message, isError = false) {
    const el = document.getElementById('dlJobStatus');
    if (!el) return;
    el.style.display = 'block';
    el.style.color = isError ? '#fca5a5' : '#94a3b8';
    el.textContent = message;
}

function _getDlParams() {
    const asset = String(document.getElementById('dlAsset')?.value || 'GOLD/USD');
    const years = parseInt(document.getElementById('dlYears')?.value || '30', 10);
    const model = String(document.getElementById('dlModel')?.value || 'gru');
    const lookback_days = parseInt(document.getElementById('dlLookbackDays')?.value || '120', 10);
    const horizon_days = parseInt(document.getElementById('dlHorizonDays')?.value || '365', 10);

    return {
        asset,
        years: Number.isFinite(years) ? years : 30,
        model,
        lookback_days: Number.isFinite(lookback_days) ? lookback_days : 120,
        horizon_days: Number.isFinite(horizon_days) ? horizon_days : 365,
    };
}

async function _startJob(endpoint, payload) {
    const data = await fetchAPI(endpoint, {
        method: 'POST',
        body: JSON.stringify(payload || {}),
    });

    if (!data) {
        _setDlJobStatus('Failed to start job (no response).', true);
        return null;
    }

    if (data.success === false) {
        _setDlJobStatus(data.error || 'Failed to start job.', true);
        return null;
    }

    if (data.job_id) {
        _setDlJobStatus(`Job started: ${data.job_id}. Waiting...`);
        _pollDlJob(data.job_id);
    } else {
        _setDlJobStatus('Job started.');
    }

    return data;
}

async function _pollDlJob(jobId) {
    if (dlJobPollTimer) {
        clearInterval(dlJobPollTimer);
        dlJobPollTimer = null;
    }

    async function tick() {
        const res = await fetchAPI(`/api/dl/job/${encodeURIComponent(jobId)}`);
        if (!res) return;

        if (res.success === false) {
            _setDlJobStatus(res.error || 'Job status error.', true);
            return;
        }

        const status = res.job?.status;
        const msg = res.job?.message || '';

        if (status === 'running') {
            _setDlJobStatus(`Job ${jobId}: running${msg ? ' — ' + msg : ''}`);
            return;
        }

        if (status === 'failed') {
            _setDlJobStatus(`Job ${jobId}: failed${msg ? ' — ' + msg : ''}`, true);
            clearInterval(dlJobPollTimer);
            dlJobPollTimer = null;
            return;
        }

        if (status === 'completed') {
            const extra = res.job?.result ? ` — ${res.job.result}` : '';
            _setDlJobStatus(`Job ${jobId}: completed${extra}`);
            clearInterval(dlJobPollTimer);
            dlJobPollTimer = null;
            return;
        }
    }

    await tick();
    dlJobPollTimer = setInterval(tick, 1500);
}

async function runDLIngest() {
    const p = _getDlParams();
    _setDlJobStatus('Starting ingest...');
    await _startJob('/api/dl/ingest', { years: p.years });
}

async function runDLTrain() {
    const p = _getDlParams();
    _setDlJobStatus('Starting training...');
    await _startJob('/api/dl/train', { asset: p.asset, model: p.model, lookback_days: p.lookback_days, horizon_days: p.horizon_days });
}

async function runDLIngestAndTrain() {
    const p = _getDlParams();
    _setDlJobStatus('Starting ingest + train...');
    await _startJob('/api/dl/ingest-train', { years: p.years, asset: p.asset, model: p.model, lookback_days: p.lookback_days, horizon_days: p.horizon_days });
}
