# Currency Analyzer - Multi-Condition Alert System Documentation

**Version**: 2.0.0 (Multi-Condition Alerts)  
**Last Updated**: January 17, 2026  
**Status**: Production Ready

---

## 1. OVERVIEW

The multi-condition alert system allows users to configure 6 different alert types per currency pair. Each alert type monitors a different market condition and can trigger independently. Users can set thresholds, parameters, and enable/disable each type individually.

---

## 2. ALERT TYPES

### 2.1 Type 1: Percentage Change (Trend Detection)

**Description**: Triggers when price changes by a configured percentage over a specified period

**When to Use**: For general trend following, momentum detection

**Parameters**:
- `change_threshold` (0.1 - 20%, default: 2%)
- `detection_period` (1 - 365 days, default: 30 days)
- `enable_trend_consistency` (boolean, default: true)

**How It Works**:
1. Fetches historical data for the specified period
2. Calculates % change from oldest to newest rate
3. If `enable_trend_consistency`, verifies 5-day uptrend pattern
4. Triggers when threshold exceeded AND trend is consistent

**Example**:
```
Pair: EUR/USD
Threshold: 2.5%
Period: 30 days
Consistency: Enabled

Triggers if: EUR/USD rises 2.5%+ in 30 days with uptrend pattern
```

**Backend Function**: `detect_trend()` in `modules/currency.py`

---

### 2.2 Type 2: Historical High

**Description**: Triggers when current price reaches highest level in specified timeframe

**When to Use**: Breakout detection, support/resistance testing, new highs trading

**Parameters**:
- `lookback_years` (1, 3, 5, 10 years; default: 5)

**How It Works**:
1. Fetches historical data for lookback period
2. Identifies maximum rate in that period
3. Compares current rate to max (within 0.1% tolerance)
4. Triggers when current ≈ max

**Example**:
```
Pair: GBP/USD
Lookback: 5 years
Historical High: 1.4250 (from 2021)
Current: 1.4248

Triggers: YES (within 0.1%)
Alert Message: "GBP/USD reached new 5-year high!"
```

**Backend Function**: `detect_historical_high()` in `modules/currency.py`

---

### 2.3 Type 3: Historical Low

**Description**: Triggers when current price reaches lowest level in specified timeframe

**When to Use**: Support level testing, capitulation signals, value hunting

**Parameters**:
- `lookback_years` (1, 3, 5, 10 years; default: 5)

**How It Works**:
1. Fetches historical data for lookback period
2. Identifies minimum rate in that period
3. Compares current rate to min (within 0.1% tolerance)
4. Triggers when current ≈ min

**Example**:
```
Pair: USD/JPY
Lookback: 3 years
Historical Low: 102.50
Current: 102.48

Triggers: YES
Alert Message: "USD/JPY reached new 3-year low!"
```

**Backend Function**: `detect_historical_low()` in `modules/currency.py`

---

### 2.4 Type 4: Price Level Bands

**Description**: Triggers when price crosses defined support/resistance levels

**When to Use**: Level-based trading, stop-loss orders, profit-taking levels

**Parameters**:
- `price_high` (upper threshold, e.g., 1.10)
- `price_low` (lower threshold, e.g., 0.95)
- `trigger_type` ('crosses_above', 'crosses_below', 'between')

**How It Works**:
1. Tracks yesterday's and today's rates
2. For 'crosses_above': triggers if previous < threshold AND current ≥ threshold
3. For 'crosses_below': triggers if previous > threshold AND current ≤ threshold
4. For 'between': triggers if current is within band

**Example**:
```
Pair: EUR/USD
Upper Level: 1.15
Lower Level: 0.90
Trigger Type: crosses_above

Previous Rate: 1.14
Current Rate: 1.1501

Triggers: YES (crossed above 1.15)
Alert: "EUR/USD crossed above 1.15!"
```

**Backend Function**: `detect_price_level_cross()` in `modules/currency.py`

---

### 2.5 Type 5: Volatility Threshold

**Description**: Triggers when price volatility spikes above or drops below normal ranges

**When to Use**: Risk management, trading opportunity detection, market stress monitoring

**Parameters**:
- `volatility_type` ('high' or 'low')

**How It Works**:
1. Calculates standard deviation of returns over last 30 days
2. Compares to standard deviation of prior 30 days
3. Calculates volatility ratio (current / average)
4. Triggers on 'high': if ratio > 2.0x (double volatility)
5. Triggers on 'low': if ratio < 0.5x (half volatility)

**Example**:
```
Pair: GBP/USD
Volatility Type: high
Recent 30-day Std Dev: 0.012 (1.2%)
Prior 30-day Std Dev: 0.006 (0.6%)
Ratio: 2.0x

Triggers: YES (volatility doubled)
Alert: "GBP/USD volatility spike detected!"
Use Case: Adjust position sizes due to increased risk
```

**Backend Function**: `detect_volatility_spike()` in `modules/currency.py`

---

### 2.6 Type 6: Moving Average Crossover

**Description**: Triggers on golden cross (bullish) or death cross (bearish) signals

**When to Use**: Trend confirmation, momentum trading, reversal detection

**Parameters**:
- `short_ma_period` (7-50 days, default: 10)
- `long_ma_period` (50-365 days, default: 50)
- `signal_type` ('golden_cross' or 'death_cross')

**How It Works**:
1. Calculates short-term moving average (SMA)
2. Calculates long-term moving average (LMA)
3. For 'golden_cross': triggers if yesterday's SMA ≤ LMA AND today's SMA > LMA
4. For 'death_cross': triggers if yesterday's SMA ≥ LMA AND today's SMA < LMA

**Example**:
```
Pair: EUR/USD
Short MA (10-day): 1.0850
Long MA (50-day): 1.0825
Signal Type: golden_cross
Yesterday: Short MA was 1.0823 (below Long MA)
Today: Short MA is 1.0850 (above Long MA)

Triggers: YES
Alert: "EUR/USD golden cross - bullish signal!"
Trading Signal: Buy setup
```

**Backend Function**: `detect_moving_average_crossover()` in `modules/currency.py`

---

## 3. CONFIGURATION

### 3.1 Via Web Interface

**Location**: Dashboard → Manage Alerts page

**Steps**:
1. Select a currency pair
2. Enable/disable the pair
3. Choose an alert type from dropdown
4. Configure parameters for that type
5. Click "Save Alert Configuration"

**Supported Pairs**:
- EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD, NZD/USD

### 3.2 Via API

**Endpoint**: `POST /api/alerts/preferences`

**Example Request**:
```json
{
  "pair": "EUR/USD",
  "enabled": true,
  "alert_type": "moving_average",
  "short_ma_period": 10,
  "long_ma_period": 50,
  "signal_type": "golden_cross"
}
```

**Example Request (Historical High)**:
```json
{
  "pair": "GBP/USD",
  "enabled": true,
  "alert_type": "historical_high",
  "lookback_years": 5
}
```

**Example Request (Price Levels)**:
```json
{
  "pair": "USD/JPY",
  "enabled": true,
  "alert_type": "price_level",
  "price_high": 115.00,
  "price_low": 100.00,
  "trigger_type": "crosses_above"
}
```

### 3.3 Get Available Conditions

**Endpoint**: `GET /api/alerts/conditions`

**Response**:
```json
{
  "percentage_change": {
    "name": "Percentage Change (Trend)",
    "description": "Alert when price changes by a percentage...",
    "parameters": {
      "change_threshold": {"type": "number", "min": 0.1, "max": 20, "default": 2},
      "detection_period": {"type": "number", "min": 1, "max": 365, "default": 30},
      "enable_trend_consistency": {"type": "boolean", "default": true}
    }
  },
  // ... other alert types
}
```

---

## 4. DATABASE SCHEMA

### 4.1 Alert Preferences Table

```sql
CREATE TABLE alert_preferences (
  pair TEXT PRIMARY KEY,
  enabled INTEGER,
  alert_type TEXT DEFAULT 'percentage_change',
  
  -- Percentage Change (Type 1)
  custom_threshold REAL,
  custom_period INTEGER,
  enable_trend_consistency INTEGER DEFAULT 1,
  
  -- Historical High/Low (Type 2-3)
  lookback_years INTEGER DEFAULT 5,
  
  -- Price Level (Type 4)
  price_high REAL,
  price_low REAL,
  trigger_type TEXT,
  
  -- Volatility (Type 5)
  volatility_type TEXT,
  
  -- Moving Average (Type 6)
  ma_short_period INTEGER DEFAULT 10,
  ma_long_period INTEGER DEFAULT 50,
  signal_type TEXT
)
```

### 4.2 Alert History Table (Enhanced)

```sql
CREATE TABLE alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pair TEXT,
  percent_change REAL,
  old_rate REAL,
  new_rate REAL,
  timestamp TEXT,
  email_sent INTEGER,
  alert_type TEXT,           -- NEW: Type of alert that triggered
  trigger_value REAL,        -- NEW: Actual value that triggered (price/change/etc)
  threshold_value REAL       -- NEW: Configured threshold value
)
```

---

## 5. MONITORING PROCESS

### 5.1 Check Interval

- **Default**: Every 15 minutes (900 seconds)
- **Configurable**: Via Settings page (5 min to 1 hour)
- **Database**: Stored in `settings` table as `check_interval`

### 5.2 Cooldown Period

- **Duration**: 1 hour per pair
- **Purpose**: Prevent alert spam from same pair
- **Implementation**: Tracked in `monitoring_state` table

### 5.3 Monitoring Loop Flow

```
START monitoring thread
  ├─ Check: monitoring_enabled = true?
  ├─ For each currency pair:
  │  ├─ Get alert preference
  │  ├─ Check: enabled?
  │  ├─ Check: cooldown expired?
  │  ├─ Get alert_type from preference
  │  ├─ SWITCH alert_type:
  │  │  ├─ 'percentage_change' → detect_trend()
  │  │  ├─ 'historical_high' → detect_historical_high()
  │  │  ├─ 'historical_low' → detect_historical_low()
  │  │  ├─ 'price_level' → detect_price_level_cross()
  │  │  ├─ 'volatility' → detect_volatility_spike()
  │  │  ├─ 'moving_average' → detect_moving_average_crossover()
  │  ├─ If triggered:
  │  │  ├─ Send email alert
  │  │  ├─ Save to alert history with alert_type
  │  │  ├─ Update last_alert_time
  ├─ Sleep check_interval seconds
  └─ REPEAT
```

---

## 6. EMAIL ALERTS

### 6.1 Alert Email Format

**Subject**: `Currency Alert: {pair} triggered {alert_type}`

**Body**:
```
Currency Alert Notification

Pair: EUR/USD
Alert Type: Percentage Change
Change: +2.5%
Old Rate: 1.0500
New Rate: 1.0763
Time: 2026-01-17 14:30:00

Configuration:
- Threshold: 2.5%
- Period: 30 days
- Trend Consistency: Enabled

Next Alert: Not before 2026-01-17 15:30:00 (1-hour cooldown)
```

### 6.2 Email Setup

**Requirements**: Gmail account with App Password

**Setup Steps**:
1. Enable 2FA on Gmail account
2. Generate App Password from account settings
3. Store as environment variable:
   ```
   GMAIL_USER=your.email@gmail.com
   GMAIL_PASSWORD=xxxx xxxx xxxx xxxx
   ```
4. Test email: Click "Test Email" in Settings page

---

## 7. BACKEND IMPLEMENTATION

### 7.1 Detection Functions

All functions in `modules/currency.py`:

```python
def detect_trend(pair, currency_pairs)
  # Returns: {is_trending, percent_change, old_rate, new_rate, start_date, end_date}

def detect_historical_high(pair, currency_pairs, lookback_years=5)
  # Returns: {is_high, current_rate, max_rate, min_rate, proximity_percent, lookback_years}

def detect_historical_low(pair, currency_pairs, lookback_years=5)
  # Returns: {is_low, current_rate, max_rate, min_rate, proximity_percent, lookback_years}

def detect_price_level_cross(pair, currency_pairs, price_high, price_low, trigger_type)
  # Returns: {is_triggered, current_rate, price_high, price_low, trigger_type}

def detect_volatility_spike(pair, currency_pairs, lookback_period=30, volatility_type='high')
  # Returns: {is_spike, current_volatility, average_volatility, volatility_ratio, volatility_type}

def detect_moving_average_crossover(pair, currency_pairs, short_period=10, long_period=50, signal_type)
  # Returns: {is_crossover, short_ma, long_ma, current_rate, signal_type, periods}
```

### 7.2 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/alerts/conditions` | List available alert types and parameters |
| POST | `/api/alerts/preferences` | Save alert configuration |
| GET | `/api/alerts/preferences` | Get all alert preferences |
| GET | `/api/alerts/preferences/<pair>` | Get specific pair's configuration |
| GET | `/api/alerts` | Get alert history |
| DELETE | `/api/alerts/clear` | Clear all alerts |

---

## 8. FRONTEND IMPLEMENTATION

### 8.1 Manage Alerts Page

**Features**:
- Alert type selector dropdown with descriptions
- Dynamic parameter inputs based on selected type
- Enable/disable toggle per pair
- Real-time parameter validation
- Save button with success notification

### 8.2 JavaScript Functions

```javascript
loadAlertPreferences()
  // Load preferences and available conditions

renderAlertPreferences(preferences, conditions)
  // Render UI with all controls

updateAlertTypeParameters(pair)
  // Dynamically update parameter inputs when type changes

saveAlertPreference(pair)
  // Collect parameters and send to backend
```

---

## 9. USAGE EXAMPLES

### 9.1 Setup 1: Trend Trader

**Goal**: Catch uptrends in momentum pairs

**EUR/USD**:
- Type: Percentage Change
- Threshold: 2%
- Period: 30 days
- Consistency: Enabled

**GBP/USD**:
- Type: Moving Average
- Short MA: 10 days
- Long MA: 50 days
- Signal: Golden Cross

**USD/JPY**:
- Type: Volatility
- Type: High (2x normal)

### 9.2 Setup 2: Level Trader

**Goal**: Trade defined support/resistance

**EUR/USD**:
- Type: Price Level
- High: 1.15
- Low: 0.90
- Trigger: Crosses Above/Below

**GBP/USD**:
- Type: Historical High (5-year)

**USD/JPY**:
- Type: Historical Low (3-year)

### 9.3 Setup 3: Long-term Investor

**Goal**: Identify multi-year extremes

**All Pairs**:
- Type: Historical High (10-year)
- Type: Historical Low (10-year)
- Threshold: Only at genuine highs/lows

---

## 10. TROUBLESHOOTING

### Issue: Alert not triggering

**Checklist**:
- Is monitoring enabled? (Settings page: Start Monitoring)
- Is the pair enabled? (Manage Alerts: toggle)
- Has cooldown expired? (1 hour minimum between alerts)
- Are thresholds reasonable? (Not too restrictive)

**Debug**: Check server logs for alert detection output

### Issue: Too many alerts

**Solutions**:
- Increase detection period (e.g., 30→60 days)
- Increase threshold (e.g., 2%→5%)
- Reduce lookback for volatility checks
- Enable trend consistency for cleaner signals

### Issue: Email not received

**Checklist**:
- Gmail user and app password configured?
- App password (not regular password) used?
- Test email button works?
- Check spam folder
- Review server logs for SMTP errors

---

## 11. PERFORMANCE NOTES

### 11.1 API Response Times

| Endpoint | Time |
|----------|------|
| `/api/alerts/conditions` | <100ms (cached) |
| `/api/alerts/preferences` | <150ms |
| Historical data fetch | 300-500ms (Frankfurter API) |
| Alert detection | 100-300ms per pair |

### 11.2 Data Usage

- Historical data requests: ~1KB per request
- Email alerts: ~2KB per email
- Database size: ~100KB for 1000 alerts

---

## 12. FUTURE ENHANCEMENTS

**Phase 2.1**:
- Alert chaining (require multiple conditions)
- SMS/Slack notifications
- Custom alert names

**Phase 2.2**:
- Backtesting engine for parameters
- ML-based parameter optimization
- Alert performance analytics

**Phase 3.0**:
- Mobile push notifications
- Calendar events on alerts
- Portfolio-level alerts (multi-pair triggers)

---

## 13. MIGRATION GUIDE

### From Single Alert Type to Multi-Condition

**Existing Data**:
- Old percentage_change alerts preserved
- `alert_type` defaults to 'percentage_change'
- Existing threshold/period parameters still work

**No data loss**: All existing configurations remain functional

**Migration Path**:
1. Update to v2.0.0+
2. Visit Manage Alerts page
3. Existing pairs show with percentage_change type
4. Select new alert types from dropdown as needed
5. Configure new parameters
6. Save

---

## 14. API REFERENCE

### Get Alert Conditions

```
GET /api/alerts/conditions
Authorization: Required (Session)

Response (200):
{
  "percentage_change": {...},
  "historical_high": {...},
  "historical_low": {...},
  "price_level": {...},
  "volatility": {...},
  "moving_average": {...}
}
```

### Update Alert Preference

```
POST /api/alerts/preferences
Authorization: Required
Content-Type: application/json

Request Body:
{
  "pair": "EUR/USD",
  "enabled": true,
  "alert_type": "moving_average",
  "short_ma_period": 10,
  "long_ma_period": 50,
  "signal_type": "golden_cross"
}

Response (200):
{
  "success": true,
  "message": "Preferences updated for EUR/USD"
}
```

---

**Document Owner**: Development Team  
**Last Review**: 2026-01-17  
**Next Review**: 2026-02-17
