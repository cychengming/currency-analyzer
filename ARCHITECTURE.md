## Currency Analyzer - Modular Architecture

### Overview
The application has been refactored from a monolithic `app.py` (~700 lines) into a clean, modular architecture with separated concerns. Each module handles a specific responsibility.

### Project Structure

```
currency-analyzer/
├── app.py                    # Main Flask application (60 lines) - entry point only
├── modules/
│   ├── __init__.py          # Module package exports
│   ├── database.py          # Database operations (SQLite CRUD)
│   ├── auth.py              # Authentication & password handling
│   ├── currency.py          # Exchange rate fetching & trend detection
│   ├── email_alert.py       # Email notification sending
│   ├── monitoring.py        # Background monitoring thread
│   └── routes.py            # All Flask API endpoints
├── static/
│   ├── login.html           # Authentication page
│   ├── dashboard.html       # Main dashboard interface
│   ├── styles.css           # Centralized styling (458 lines)
│   ├── auth.js              # Frontend authentication logic
│   ├── utils.js             # Shared frontend utilities
│   ├── dashboard.js         # Dashboard initialization & logic
│   └── pages/               # Page-specific modules (extensible)
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Docker Compose setup
├── requirements.txt         # Python dependencies
└── data/                    # Database persistence volume
    └── currency_monitor.db
```

### Module Descriptions

#### `modules/database.py` (Data Access Layer)
- **Purpose**: SQLite database operations
- **Key Functions**:
  - `init_db()` - Create tables and initialize schema
  - `get_setting() / set_setting()` - Configuration management
  - `save_alert() / get_alert_history()` - Alert persistence
  - `get_alert_preference() / set_alert_preference()` - Per-pair settings
  - `get_monitoring_state() / set_monitoring_state()` - Trend tracking
- **Responsibility**: All database I/O, no business logic

#### `modules/auth.py` (Authentication Layer)
- **Purpose**: User authentication and password security
- **Key Functions**:
  - `hash_password()` - PBKDF2-HMAC-SHA256 hashing with salt
  - `verify_password()` - Password verification
  - `register_user()` - New user creation
  - `authenticate_user()` - Login validation
  - `login_required()` - Flask decorator for protected routes
- **Responsibility**: All security and authentication logic

#### `modules/currency.py` (Business Logic)
- **Purpose**: Currency data fetching and analysis
- **Key Functions**:
  - `fetch_live_rates()` - Get current exchange rates from Frankfurter API
  - `fetch_historical_data()` - Get historical price data
  - `detect_trend()` - Analyze price trends with configurable thresholds
  - `parse_pair()` - Split currency pair strings
- **Responsibility**: All currency analysis and external API calls

#### `modules/email_alert.py` (Notifications)
- **Purpose**: Email alert notifications
- **Key Functions**:
  - `send_email_alert()` - Send HTML-formatted alerts via Gmail SMTP
- **Responsibility**: Email delivery and formatting
- **Config**: Reads from `GMAIL_USER` and `GMAIL_PASSWORD` environment variables

#### `modules/monitoring.py` (Background Processing)
- **Purpose**: Background monitoring thread management
- **Key Functions**:
  - `monitoring_loop()` - Continuous trend checking
  - `start_monitoring()` - Start background thread
  - `stop_monitoring()` - Stop background thread
  - `is_monitoring_active()` - Check thread status
- **Responsibility**: Async processing and thread lifecycle

#### `modules/routes.py` (API Layer)
- **Purpose**: All Flask API endpoints organized by concern
- **Route Groups**:
  - **Authentication** (`/api/auth/*`) - Login, register, logout, status
  - **Currency Data** (`/api/live-rates`, `/api/historical/*`) - Exchange rates
  - **Settings** (`/api/settings`) - Global configuration
  - **Alerts** (`/api/alerts/*`) - History and preferences
  - **Monitoring** (`/api/monitoring/*`) - Control monitoring state
- **Key Function**: `create_routes(app, currency_pairs)` - Register all routes
- **Responsibility**: HTTP request handling, no business logic

#### `app.py` (Main Application)
- **Purpose**: Flask app initialization and startup orchestration
- **Lines**: ~60 (down from ~700)
- **Imports**: All modules and orchestrates initialization
- **Startup Flow**:
  1. Initialize Flask app with security config
  2. Initialize database
  3. Register all routes via `create_routes()`
  4. Start monitoring thread
  5. Run development server

### Benefits of Modular Architecture

1. **Separation of Concerns**
   - Each module has a single, clear responsibility
   - Easier to understand and maintain each component

2. **Testability**
   - Can test each module independently
   - Mock dependencies easily for unit tests

3. **Reusability**
   - Modules can be imported in other projects
   - No coupling between business logic and Flask

4. **Scalability**
   - Easy to extend with new features
   - Database layer can be swapped without affecting routes

5. **Debugging**
   - Errors are easier to locate and fix
   - Clear import dependencies

6. **Team Development**
   - Multiple developers can work on different modules simultaneously
   - Reduces merge conflicts

### Data Flow

```
HTTP Request
    ↓
routes.py (Request handler)
    ↓
auth.py (Optional: Verify login_required)
    ↓
Business Logic (currency.py, database.py, etc.)
    ↓
database.py (Data persistence)
    ↓
SQLite (currency_monitor.db)
```

### Configuration Hierarchy

```
Environment Variables (Docker)
    ↓
modules/database.py (DATABASE path, data directory)
modules/email_alert.py (GMAIL credentials)
    ↓
database.py (Default settings table)
    ↓
API: /api/settings (User-configurable settings)
```

### Deployment

**Docker Build Process**:
1. Python 3.11-slim base image
2. Install dependencies from `requirements.txt`
3. Copy `app.py`, `modules/`, `static/`
4. Create `/app/data` directory for persistence
5. Expose port 5000

**Docker Run Command**:
```bash
docker run -d --name currency-analyzer \
  -p 5000:5000 \
  -v ${PWD}/data:/app/data \
  --restart unless-stopped \
  currency-analyzer
```

**Volume Mounting**: 
- Host: `./data/`
- Container: `/app/data/`
- Ensures database persists across container restarts

### Module Dependencies Graph

```
app.py (entry point)
  ├── modules/__init__.py (exports)
  │   ├── modules/database.py (no dependencies)
  │   ├── modules/auth.py (imports database.py)
  │   ├── modules/currency.py (imports database.py)
  │   ├── modules/email_alert.py (imports database.py)
  │   ├── modules/monitoring.py (imports all others)
  │   └── modules/routes.py (imports all others)
```

### Adding New Features

To add a new feature:

1. **New Module** - Create `modules/feature.py`
2. **Export** - Add to `modules/__init__.py`
3. **Routes** - Add route handler to `modules/routes.py`
4. **Frontend** - Add page to `static/pages/feature.js`

Example:
```python
# modules/feature.py
def get_feature_data():
    from modules.database import get_setting
    # Business logic here
    return data

# modules/routes.py
@app.route('/api/feature/data', methods=['GET'])
@login_required
def api_feature_data():
    data = get_feature_data()
    return jsonify(data)
```

### Performance Characteristics

- **Startup Time**: ~2-3 seconds
- **Database Queries**: 1-10ms (SQLite on local disk)
- **API Response**: 100-500ms (includes external API calls)
- **Background Monitoring**: Configurable interval (default 15 minutes)
- **Memory Usage**: ~150-200MB running

### Future Improvements

- [ ] Add API documentation (Swagger/OpenAPI)
- [ ] Implement caching layer (Redis)
- [ ] Add comprehensive unit tests
- [ ] Migrate to async/await with asyncio
- [ ] Add database migration tool (Alembic)
- [ ] Implement logging module
- [ ] Add rate limiting middleware
- [ ] Create admin dashboard for system monitoring

### Git History

- Commit `fa9317b` - Refactor: Modularize app.py
- Commit `9ae21e4` - Update: Include modules in Docker build
- Previous: Multiple commits for features and bug fixes
