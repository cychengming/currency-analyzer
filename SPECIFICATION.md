# Currency Analyzer - Specification Document

**Project**: Currency Market Analyzer  
**Version**: 2.0.0 (Modular Architecture)  
**Last Updated**: January 17, 2026  
**Status**: In Development

---

## 1. OVERVIEW

Currency Market Analyzer is a real-time currency exchange rate monitoring system with email alerts, trend detection, and historical analysis capabilities. The application features a modular backend architecture and responsive frontend dashboard.

### Tech Stack
- **Backend**: Python 3.11, Flask, SQLite
- **Frontend**: Vanilla JavaScript, Chart.js, HTML5/CSS3
- **Deployment**: Docker, Docker Compose
- **External APIs**: Frankfurter API (exchange rates)

---

## 2. CURRENT FEATURES (WORKING)

### 2.1 Authentication System
- ✅ User registration (3+ char username, 6+ char password)
- ✅ Secure login with PBKDF2-HMAC-SHA256 password hashing
- ✅ Session-based authentication with HTTP-only cookies
- ✅ Logout functionality
- ✅ Protected API endpoints with @login_required decorator

### 2.2 Live Exchange Rates
- ✅ Real-time rates for 7 currency pairs:
  - EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD, NZD/USD
- ✅ Live rate cards with daily change percentage
- ✅ Rate update interval: 1 minute (configurable)
- ✅ Frankfurter API integration

### 2.3 Historical Data & Charts
- ✅ Chart.js line chart visualization
- ✅ Configurable timeframe with 3 dimensions:
  - **Days**: 7, 14, 30, 60, 90, 180, 365
  - **Weeks**: 4, 8, 12, 24, 52
  - **Months**: 1, 3, 6, 12, 24
- ✅ Automatic day conversion (weeks × 7, months × 30)
- ✅ URL encoding for pair names (EUR%2FUSD)

### 2.4 Alert System
- ✅ Per-pair alert preferences (enable/disable)
- ✅ Custom threshold per pair (% change)
- ✅ Custom detection period per pair (days)
- ✅ Alert history tracking with timestamps
- ✅ Email alert notifications via Gmail SMTP
- ✅ Global settings: threshold, period, check interval

### 2.5 Trend Detection
- ✅ Uptrend detection algorithm
- ✅ Consistency check (5-day lookback)
- ✅ Cooldown period (1 hour between alerts)
- ✅ Alert history storage

### 2.6 Monitoring Thread
- ✅ Background monitoring (configurable interval)
- ✅ Start/stop controls via API
- ✅ Monitoring status endpoint
- ✅ Thread-safe database operations

### 2.7 Dashboard UI
- ✅ Multi-page layout (Overview, Alert History, Manage Alerts, Settings)
- ✅ Dark theme design (#0f172a background)
- ✅ Responsive grid layout
- ✅ Real-time status indicator
- ✅ Login/Register forms with validation

### 2.8 Database
- ✅ SQLite with 5 tables: settings, alerts, monitoring_state, alert_preferences, users
- ✅ Volume persistence (data/ directory)
- ✅ Database initialization on startup

### 2.9 Modular Architecture
- ✅ Separated concerns into 7 modules
- ✅ modules/database.py - Data access layer
- ✅ modules/auth.py - Authentication
- ✅ modules/currency.py - Business logic
- ✅ modules/email_alert.py - Notifications
- ✅ modules/monitoring.py - Background processing
- ✅ modules/routes.py - API endpoints

---

## 3. KNOWN ISSUES

### 3.1 Critical Issues
| ID | Issue | Impact | Status |
|----|-------|--------|--------|
| BUG-001 | Historical chart sometimes empty on initial load | High | Open |
| BUG-002 | URL encoding causes 404 errors in some cases | Medium | Partially Fixed |
| BUG-003 | Email alerts require Gmail app password setup | High | Documentation Needed |

### 3.2 Medium Priority Issues
| ID | Issue | Impact | Status |
|----|-------|--------|--------|
| BUG-004 | Chart data not validating for null/empty | Medium | Open |
| BUG-005 | No loading spinner during chart fetch | Low | Open |
| BUG-006 | Session timeout not explicitly handled | Medium | Open |
| BUG-007 | No error logging for API failures | Medium | Open |

### 3.3 Low Priority Issues
| ID | Issue | Impact | Status |
|----|-------|--------|--------|
| BUG-008 | Missing timestamps on some alert records | Low | Open |
| BUG-009 | No pagination for alert history | Low | Open |
| BUG-010 | Chart legend could be more informative | Low | Open |

---

## 4. ISSUE FIX ROADMAP

### 4.1 High Priority Fixes
#### FIX-001: Historical Chart Empty on Load
**Problem**: Chart sometimes fails to render after selecting a pair  
**Root Cause**: Empty data array from API or race condition  
**Solution**:
- Add data validation before chart rendering
- Implement loading state indicator
- Add error boundary with fallback UI
- Verify timeframe calculation logic

**Implementation**:
```javascript
function updateChart(data) {
    if (!data || data.length === 0) {
        showChartEmpty();
        return;
    }
    // ... render chart
}
```

#### FIX-002: URL Encoding Issues
**Problem**: Pair names with "/" cause route matching failures  
**Root Cause**: Flask route parameter handling  
**Solution**:
- Ensure frontend encodes with encodeURIComponent()
- Backend decodes with unquote()
- Add unit tests for special characters

#### FIX-003: Email Alert Configuration
**Problem**: Users struggle to configure Gmail credentials  
**Solution**:
- Create setup wizard modal
- Add validation endpoint
- Document Gmail App Passwords process
- Add test email button (already exists)

### 4.2 Medium Priority Fixes
#### FIX-004: Add Comprehensive Logging
**Implementation**:
- Create modules/logging.py
- Add debug logging to all API calls
- Log database operations
- Track error contexts

#### FIX-005: Session Management
**Implementation**:
- Add session timeout warning
- Auto-logout after 7 days (configurable)
- Refresh session on activity

#### FIX-006: Data Validation
**Implementation**:
- Validate all API responses
- Type checking for chart data
- Handle null/undefined gracefully

---

## 5. NEW FEATURES (PLANNED)

### 5.1 Phase 1: Enhanced Charting
| Feature | Priority | Effort | Status |
|---------|----------|--------|--------|
| Multiple pair comparison chart | High | 8h | Planned |
| Moving averages overlay | High | 6h | Planned |
| MACD indicators | Medium | 8h | Planned |
| Relative Strength Index (RSI) | Medium | 8h | Planned |
| Support/Resistance levels | Low | 10h | Planned |

**Spec: Multiple Pair Comparison**
```
Frontend:
- Add "Compare Pairs" button
- Multi-select pair picker
- Different colored lines per pair
- Legend with pair names

Backend:
- New endpoint: /api/historical/compare
- Accept multiple pairs
- Return merged datasets
```

### 5.2 Phase 2: Advanced Alerts (UPDATED - Multi-Condition System)
| Feature | Priority | Effort | Status |
|---------|----------|--------|--------|
| Multi-condition alert types (6 types) | High | 12h | In Progress |
| SMS notifications | Medium | 8h | Planned |
| Slack webhook integration | Medium | 6h | Planned |
| Custom alert names/descriptions | Low | 4h | Planned |

**Spec: Multi-Condition Alert System**

**Alert Type 1: Percentage Change (Current - Enhanced)**
```
Condition: Price change exceeds threshold % over detection period
Parameters:
  - change_threshold: 0.1 - 20% (default: 2%)
  - detection_period: 1 - 365 days (default: 30 days)
  - trend_consistency: boolean (requires 5-day uptrend consistency)
Example: EUR/USD rises 3% within 30 days with uptrend pattern
```

**Alert Type 2: Historical High (NEW)**
```
Condition: Current price reaches new 5-year high
Parameters:
  - lookback_years: 1, 3, 5, 10 (default: 5)
  - proximity: 0-5% tolerance to all-time high (default: 0% - exact match)
Example: EUR/USD hits highest price in 5 years
Database Changes:
  ADD COLUMN alert_high_5yr_enabled BOOLEAN (or use alert_conditions JSON)
Calculation: Fetch 5-year historical data, find max, compare with current
```

**Alert Type 3: Historical Low (NEW)**
```
Condition: Current price reaches new 5-year low
Parameters:
  - lookback_years: 1, 3, 5, 10 (default: 5)
  - proximity: 0-5% tolerance (default: 0%)
Example: EUR/USD drops to lowest price in 5 years
```

**Alert Type 4: Volatility Threshold (NEW)**
```
Condition: Price swings (range) exceed normal volatility
Parameters:
  - volatility_type: 'high' or 'low'
  - lookback_period: 7 - 365 days (default: 30 days)
  - std_dev_threshold: 1-3x (default: 2x above average std dev)
Example: EUR/USD volatility 50% higher than 30-day average
Calculation: Calculate standard deviation of returns over period
```

**Alert Type 5: Price Level Bands (NEW)**
```
Condition: Price crosses above or below user-defined levels
Parameters:
  - price_high: Upper threshold (e.g., 1.10 for EUR/USD)
  - price_low: Lower threshold (e.g., 0.95 for EUR/USD)
  - trigger_type: 'crosses_above' | 'crosses_below' | 'between'
Example: Alert when EUR/USD falls below 0.95 or rises above 1.10
Database Changes:
  ADD COLUMN price_high REAL
  ADD COLUMN price_low REAL
  ADD COLUMN trigger_type TEXT
```

**Alert Type 6: Moving Average Crossover (NEW)**
```
Condition: Short-term MA crosses above/below long-term MA
Parameters:
  - short_ma_period: 7 - 50 days (default: 10 days)
  - long_ma_period: 50 - 365 days (default: 50 days)
  - signal_type: 'golden_cross' (short > long) | 'death_cross' (short < long)
Example: EUR/USD 10-day MA crosses above 50-day MA (bullish signal)
Calculation: Calculate both MAs, detect crossover
```

**Database Schema Changes:**
```sql
-- Replace single alert_preferences with flexible system
ALTER TABLE alert_preferences ADD COLUMN alert_conditions JSON;
-- OR: Add multiple condition columns for simpler approach:

ALTER TABLE alert_preferences ADD COLUMN alert_type TEXT DEFAULT 'percentage_change';
ALTER TABLE alert_preferences ADD COLUMN change_threshold REAL;
ALTER TABLE alert_preferences ADD COLUMN detection_period INTEGER;
ALTER TABLE alert_preferences ADD COLUMN lookback_years INTEGER;
ALTER TABLE alert_preferences ADD COLUMN price_high REAL;
ALTER TABLE alert_preferences ADD COLUMN price_low REAL;
ALTER TABLE alert_preferences ADD COLUMN trigger_type TEXT;
ALTER TABLE alert_preferences ADD COLUMN volatility_type TEXT;
ALTER TABLE alert_preferences ADD COLUMN ma_short_period INTEGER;
ALTER TABLE alert_preferences ADD COLUMN ma_long_period INTEGER;
ALTER TABLE alert_preferences ADD COLUMN signal_type TEXT;
ALTER TABLE alert_preferences ADD COLUMN enable_trend_consistency BOOLEAN;

-- Enhanced alerts table for history tracking
ALTER TABLE alerts ADD COLUMN alert_type TEXT;
ALTER TABLE alerts ADD COLUMN trigger_value REAL;  -- actual price/change that triggered
ALTER TABLE alerts ADD COLUMN threshold_value REAL;  -- configured threshold
```

**API Changes:**
```
POST /api/alerts/preferences
{
  "pair": "EUR/USD",
  "enabled": true,
  "alert_type": "percentage_change",  // or "historical_high", "volatility", etc.
  
  // Percentage Change (Type 1)
  "change_threshold": 2.5,
  "detection_period": 30,
  "enable_trend_consistency": true,
  
  // Historical High/Low (Type 2-3)
  "lookback_years": 5,
  
  // Volatility (Type 4)
  "volatility_type": "high",
  
  // Price Levels (Type 5)
  "price_high": 1.10,
  "price_low": 0.95,
  "trigger_type": "crosses_above",
  
  // Moving Average (Type 6)
  "ma_short_period": 10,
  "ma_long_period": 50,
  "signal_type": "golden_cross"
}

GET /api/alerts/conditions  -- Returns available condition types and parameters
```

**Frontend UI Changes:**
```
Manage Alerts page redesign:
1. Pair selector (already exists)
2. Alert Type dropdown:
   - Percentage Change (current trend detection)
   - Historical High/Low
   - Volatility Threshold
   - Price Level Bands
   - Moving Average Crossover
3. Dynamic parameter panel (shows fields based on alert type):
   - Percentage Change: threshold, period, consistency toggle
   - Historical: lookback_years selector
   - Volatility: type selector (high/low)
   - Price Levels: high/low inputs, trigger type selector
   - Moving Average: short/long periods, signal type selector
4. Enable/Disable toggle
5. Save button
```

**Example Alert Combinations:**
```
User Setup 1: EUR/USD
- Type: Historical High (5-year)
- Type: Price Level Bands (crosses above 1.15 or below 0.90)
- Type: Volatility High (2x above normal)
All enabled = sends alert if ANY condition triggers

User Setup 2: GBP/USD
- Type: Percentage Change (3% in 20 days with trend)
- Type: Moving Average (10-day > 50-day golden cross)
- Type: Price Level (between 1.25 and 1.35)
Multiple conditions = more specific, fewer false alerts
```

### 5.3 Phase 3: Data Export & Analysis
| Feature | Priority | Effort | Status |
|---------|----------|--------|--------|
| Export alerts to CSV | High | 4h | Planned |
| Export chart data to JSON | High | 2h | Planned |
| PDF report generation | Medium | 10h | Planned |
| Historical performance analytics | Medium | 12h | Planned |

**Spec: CSV Export**
```
Endpoint: GET /api/alerts/export?format=csv
Response: CSV file download
Columns: timestamp, pair, percent_change, old_rate, new_rate, email_sent
```

### 5.4 Phase 4: Advanced Features
| Feature | Priority | Effort | Status |
|---------|----------|--------|--------|
| Dark/Light theme toggle | Low | 3h | Planned |
| Mobile app (React Native) | Low | 80h | Planned |
| Portfolio management | Medium | 20h | Planned |
| Backtesting engine | Medium | 30h | Planned |
| Machine learning predictions | Low | 50h | Planned |

### 5.5 Phase 5: DevOps & Infrastructure
| Feature | Priority | Effort | Status |
|---------|----------|--------|--------|
| Kubernetes deployment config | Medium | 8h | Planned |
| CI/CD pipeline (GitHub Actions) | High | 6h | Planned |
| Automated testing (pytest, Jest) | High | 20h | Planned |
| API documentation (Swagger) | Medium | 6h | Planned |
| Health check endpoint | Medium | 2h | Planned |

---

## 6. TECHNICAL DEBT & IMPROVEMENTS

### 6.1 Backend Refactoring
- [ ] Add comprehensive type hints (Python 3.10+ style)
- [ ] Implement async/await with asyncio
- [ ] Add request validation middleware
- [ ] Migrate to SQLAlchemy ORM
- [ ] Add database migration tool (Alembic)

### 6.2 Frontend Improvements
- [ ] Convert to TypeScript
- [ ] Move to Vue.js or React for better component management
- [ ] Add unit testing (Jest)
- [ ] Implement PWA features (offline support)
- [ ] Add accessibility features (WCAG 2.1 AA)

### 6.3 Testing
- [ ] Unit tests for all modules (target: 80% coverage)
- [ ] Integration tests for API endpoints
- [ ] End-to-end tests with Selenium
- [ ] Load testing with k6 or locust
- [ ] Security testing (OWASP)

### 6.4 Documentation
- [ ] API documentation (Swagger/OpenAPI)
- [ ] User manual (screenshots, tutorials)
- [ ] Developer guide (architecture deep-dive)
- [ ] Deployment guide (AWS, GCP, Azure)
- [ ] Troubleshooting guide

---

## 7. IMPLEMENTATION CHECKLIST

### 7.1 Current Sprint (v2.0.0)
- [x] Modularize app.py into separate modules
- [x] Add timeframe controls (days/weeks/months)
- [x] Fix historical chart display
- [ ] Fix BUG-004 (chart data validation)
- [ ] Add loading spinner during fetch
- [ ] Write integration tests

### 7.2 Next Sprint (v2.1.0)
- [ ] Implement FIX-004 (logging module)
- [ ] Add session timeout handling
- [ ] Create email setup wizard
- [ ] Add health check endpoint
- [ ] Write API documentation

### 7.3 Future Releases (v3.0.0+)
- [ ] Multiple pair comparison
- [ ] Technical indicators
- [ ] Price level alerts
- [ ] Export functionality
- [ ] Mobile app

---

## 8. TESTING STRATEGY

### 8.1 Unit Tests
**Backend** (Python):
```bash
pytest tests/test_auth.py -v
pytest tests/test_currency.py -v
pytest tests/test_database.py -v
```

**Frontend** (JavaScript):
```bash
jest tests/dashboard.test.js
jest tests/utils.test.js
```

### 8.2 Integration Tests
```bash
pytest tests/integration/test_api_endpoints.py
pytest tests/integration/test_auth_flow.py
```

### 8.3 E2E Tests
```bash
pytest tests/e2e/test_user_journey.py --headless
```

---

## 9. DEPLOYMENT CHECKLIST

### 9.1 Pre-Deployment
- [ ] All tests passing (100%)
- [ ] Code review completed
- [ ] Security scan passed
- [ ] Performance benchmarks acceptable
- [ ] Documentation updated

### 9.2 Deployment Steps
```bash
git tag v2.0.0
git push origin main --tags
docker build -t currency-analyzer:2.0.0 .
docker push registry.example.com/currency-analyzer:2.0.0
kubectl apply -f k8s/deployment.yaml
```

### 9.3 Post-Deployment
- [ ] Verify all endpoints responding
- [ ] Check database integrity
- [ ] Monitor error logs
- [ ] Test email alerts
- [ ] Verify data persistence

---

## 10. API ENDPOINTS REFERENCE

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `POST /api/auth/logout` - Logout user
- `GET /api/auth/status` - Check auth status

### Currency Data
- `GET /api/live-rates` - Get current rates
- `GET /api/historical/<pair>/<days>` - Get historical data

### Alerts
- `GET /api/alerts` - Get alert history
- `POST /api/alerts/preferences` - Update alert settings
- `GET /api/alerts/preferences` - Get all preferences
- `DELETE /api/alerts/clear` - Clear alert history

### Settings
- `GET /api/settings` - Get settings
- `POST /api/settings` - Update settings

### Monitoring
- `POST /api/monitoring/start` - Start monitoring
- `POST /api/monitoring/stop` - Stop monitoring
- `GET /api/monitoring/status` - Get status
- `POST /api/test-email` - Send test email

---

## 11. DATABASE SCHEMA

### tables
- **settings**: Global configuration (key-value store)
- **users**: User accounts with hashed passwords
- **alerts**: Alert history with timestamps
- **alert_preferences**: Per-pair alert settings
- **monitoring_state**: Last alert timestamp per pair

---

## 12. ENVIRONMENT VARIABLES

```bash
# Application
FLASK_ENV=production
SECRET_KEY=<generate-with-secrets.token_hex(32)>
DATABASE=/app/data/currency_monitor.db

# Email
GMAIL_USER=your.email@gmail.com
GMAIL_PASSWORD=xxxx xxxx xxxx xxxx  # App password, not regular password

# Server
HOST=0.0.0.0
PORT=5000
```

---

## 13. SUCCESS METRICS

| Metric | Target | Current |
|--------|--------|---------|
| API Response Time | <500ms | ~300ms |
| Chart Rendering | <2s | ~1.5s |
| Data Accuracy | 99.9% | 99.8% |
| Uptime | 99.5% | TBD |
| User Satisfaction | >4.5/5 | N/A |

---

## 14. GLOSSARY

- **Timeframe**: Duration for historical data (days, weeks, months)
- **Trend**: Uptrend when price increases by threshold % consistently
- **Cooldown**: Wait period before sending another alert (1 hour)
- **Alert Preference**: Per-pair configuration for alert behavior
- **Monitoring State**: Tracks last alert time to enforce cooldown

---

## 15. REVISION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2026-01-17 | Modular architecture, 3D timeframe controls |
| 1.0.0 | 2026-01-10 | Initial monolithic version |

---

**Document Owner**: Development Team  
**Last Review**: 2026-01-17  
**Next Review**: 2026-02-17
