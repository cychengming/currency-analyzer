---
name: finance
description: Finance/quant domain guidance for this repo (FX + commodities monitoring, alert signals, indicators, risk metrics, and backtesting). Keywords: forex, FX, exchange rates, commodities, OHLC, backtest, volatility, drawdown, Sharpe, SMA/EMA, RSI, MACD, position sizing.
---

# Finance Skill (Currency Analyzer)

This skill provides domain knowledge and implementation guidance for finance-related work in this repository.

It is optimized for:
- FX + commodity quote ingestion (live + historical)
- Alert signal detection (trend/high/low/levels/volatility/MA)
- Simple, explainable backtests on daily bars
- Risk/return metrics and technical indicators

## When to invoke

Use this skill when the user asks about (or the task implies):
- FX / forex pairs, exchange rates, commodities, quote normalization
- Technical indicators (SMA/EMA, MA crossover, RSI, MACD, Bollinger Bands)
- Volatility, correlation, drawdown, Sharpe/Sortino, CAGR, returns
- Backtesting rules, entry/exit logic, stop-loss/take-profit, PnL
- Position sizing, risk management, exposure, hedging (implementation-focused)
- Forecasting/econometrics/ML for markets (especially the optional DL pipeline)

## Guardrails (important)

- Do not give personalized investment advice or tell the user what to buy/sell/hold.
	- If asked “should I trade X?”, respond with a brief disclaimer and pivot to tooling: metrics, scenarios, and how to implement analysis in code.
- Be explicit about assumptions (data source, frequency, calendar vs trading days, fees/slippage, risk‑free rate, currency of account).
- Avoid overclaiming: results depend on data quality and methodology.
- Prefer implementable, testable code and clear definitions over market “hot takes”.

## Repo map (where finance logic lives)

- `modules/currency.py`
	- Fetching: `fetch_live_rates`, `fetch_historical_data`, `fetch_historical_ohlc_data`
	- Existing detectors:
		- `detect_trend` (percentage change + consistency)
		- `detect_historical_high` / `detect_historical_low`
		- `detect_price_level_cross`
		- `detect_volatility_spike`
		- `detect_moving_average_crossover`
		- `detect_long_term_uptrend` (combined confirmations)
- `modules/backtest.py`
	- Simple backtest engine (daily close evaluation; optional OHLC use for SL/TP checks)
	- Entry signal types align with alert concepts (e.g., MA crossover, price levels, trend)
- `modules/monitoring.py`
	- Background monitoring loop; routes by `alert_type`; enforces cooldown
- `modules/database.py`
	- `alert_preferences` schema stores per-pair parameters
	- `alerts` history stores triggered info
- `modules/routes.py`
	- `/api/historical/<pair>/<days>`, `/api/historical-ohlc/<pair>/<days>`, `/api/backtest`
	- Uses `<path:pair>` + URL decode to handle pairs like `EUR/USD`

## Data conventions (follow these)

- Pair format: `BASE/QUOTE` (e.g., `EUR/USD`). Commodities also use `BASE/USD` (e.g., `GOLD/USD`).
- Historical series shape:
	- Close-only: list of `{ "date": "YYYY-MM-DD", "rate": <float> }`
	- OHLC: list of `{ "date": ..., "open": ..., "high": ..., "low": ..., "close": ..., "rate": <close> }`
- Sources:
	- FX: frankfurter.app (primary), Yahoo chart API fallback
	- Commodities: Yahoo Finance (may be blocked), Stooq fallback
- URL encoding:
	- Frontend should use `encodeURIComponent(pair)`
	- Backend decodes with `unquote(pair)`

## Common finance definitions (be consistent)

### Returns

- Simple return: $r_t = \frac{P_t}{P_{t-1}} - 1$
- Percent return: $100\,r_t$
- Log return: $\ell_t = \ln\left(\frac{P_t}{P_{t-1}}\right)$

Prefer simple returns when matching existing repo code (it uses percent returns in volatility).

### Volatility

- Sample standard deviation of returns: $\sigma = \mathrm{std}(r)$
- Annualization (only if asked):
	- Trading days: multiply by $\sqrt{252}$
	- Calendar days: multiply by $\sqrt{365}$

State clearly which one you use.

### Drawdown

For equity curve $E_t$:
- Running peak: $M_t = \max_{u \le t} E_u$
- Drawdown: $DD_t = \frac{E_t}{M_t} - 1$
- Max drawdown: $\min_t DD_t$

### Sharpe ratio (only if requested)

For excess returns $r_t - r_f$:
- $\mathrm{Sharpe} = \frac{\mu}{\sigma} \times \sqrt{A}$ where $A$ is annualization factor.

## Implementation guidance

### Default to minimal dependencies

The core web app only depends on Flask + requests. Prefer pure-Python implementations (no numpy/pandas) unless the user explicitly wants heavier analytics.

If ML/forecasting is requested, check the optional DL requirements (`requirements-dl.txt`, `requirements-dl-train.txt`).

### Add a new indicator or alert type (checklist)

When implementing a new alert/indicator, keep changes consistent with the existing flow:

1. **Define parameters**
	 - Add new fields to `alert_preferences` in `modules/database.py` if you need to store per-pair params.
	 - Add migration logic to `_apply_schema_migrations()` so existing DBs upgrade safely.

2. **Implement detector**
	 - Add a `detect_<name>()` function in `modules/currency.py`.
	 - Return a dict that includes a single boolean flag (`is_<triggered>`) plus values needed for UI/email/history.
	 - Be defensive: handle empty data, missing rates, division by zero.

3. **Wire monitoring**
	 - Add a new `elif alert_type == '<your_type>'` branch in `modules/monitoring.py`.
	 - Ensure the global “triggered?” check includes your detector’s boolean flag.

4. **Expose via API/UI (if needed)**
	 - Update endpoints in `modules/routes.py` that set/get preferences.
	 - Update frontend config UI under `static/pages/` (especially Manage Alerts) to collect params.

5. **Document**
	 - Update `ALERT_SYSTEM.md` with the new condition, parameters, and examples.

### Backtesting best practices (for code you write here)

- Avoid look-ahead bias:
	- Entry/exit decisions for day $t$ may only use data up to $t$.
- Decide execution price and state it:
	- This repo’s backtest evaluates on daily closes; SL/TP can use OHLC intraday extremes when present.
- Handle edge cases:
	- Missing candles, repeated dates, zero/None prices
	- Weekend/holiday gaps (FX often has missing weekend bars)
- Keep it explainable by default; add complexity (fees, slippage, leverage) only if requested.

## How to respond to common user intents

### “Explain this indicator / alert”

- Provide a short definition.
- Provide the exact formula and the required inputs.
- Point to where it is implemented (or where you would implement it) in this repo.

### “Add RSI/MACD/Bollinger”

- Clarify timeframe + price series used (close vs OHLC).
- Implement in `modules/currency.py` with pure Python.
- If it becomes an alert type, follow the alert-type checklist.

### “Should I trade X?”

- Reply: you can’t provide investment advice.
- Offer to help compute/visualize risk metrics, run backtests, or set alerts.
- Ask for neutral requirements (pair, timeframe, rule definition, risk tolerance as inputs for sizing—not recommendations).

## Examples (good outputs)

- “Implement a 14-day RSI on daily closes, return it via an API route, and plot it on the Chart.js view; handle missing data and keep dependencies minimal.”
- “Add a new alert type for Bollinger Band breakout with parameters: period and stdev multiplier; persist per pair; document in `ALERT_SYSTEM.md`.”
- “Extend backtesting to compute max drawdown and Sharpe for the equity curve; clearly state annualization assumptions.”