# Test Coverage Analysis for Heim

## Executive Summary

This is a home monitoring system focused on temperature and power usage, built with FastAPI (Python 3.14+), PostgreSQL, and integrations with Aqara smart home devices and YR weather forecasts. The test suite uses **pytest** with async support, but test coverage is limited to core functionality.

**Current State:**
- 24 test functions across 10 test files
- ~575 lines of test code
- Tests cover: authentication, accounts, sessions, basic database operations, and Aqara query/task operations

**Major Gaps:**
- No frontend (web UI) tests
- No external API client tests (YR weather, Aqara client)
- No task executor tests
- No forecast query tests
- No sensor query tests
- No CLI command tests

---

## Current Test Coverage by Module

| Module | Coverage Status | Test Count | Notes |
|--------|----------------|------------|-------|
| `auth/api.py` | ✅ Well tested | 6 | All auth endpoints covered |
| `accounts/queries.py` | ⚠️ Partial | 2 | Account/location creation tested |
| `accounts/utils.py` | ✅ Well tested | 2 | Password hashing tested |
| `auth/queries.py` | ✅ Well tested | 3 | Session CRUD tested |
| `db/__init__.py` | ✅ Well tested | 3 | fetch/fetchrow/fetchval tested |
| `tasks/queries.py` | ⚠️ Partial | 2 | Scheduling tested, execution not |
| `integrations/aqara/queries.py` | ⚠️ Partial | 3 | Account/sensor creation tested |
| `integrations/aqara/tasks.py` | ⚠️ Partial | 1 | update_sensor_data tested with mocks |
| `frontend/views.py` | ❌ Not tested | 0 | - |
| `forecasts/queries.py` | ❌ Not tested | 0 | - |
| `sensors/queries.py` | ❌ Not tested | 0 | - |
| `integrations/yr/client.py` | ❌ Not tested | 0 | - |
| `integrations/aqara/client.py` | ❌ Not tested | 0 | - |
| `integrations/aqara/services.py` | ❌ Not tested | 0 | - |
| `tasks/executor.py` | ❌ Not tested | 0 | - |
| `tasks/base.py` | ❌ Not tested | 0 | - |

---

## Priority 1: High-Impact Test Additions

### 1. Frontend Views Tests (`heim/frontend/views.py`)

**Why:** The frontend is the user-facing part of the application. Login/logout flows and the location overview are critical paths.

**Suggested tests:**
```python
# tests/test_frontend_views.py

async def test_login_page_renders():
    """GET /login/ should return 200 with login form"""

async def test_login_success():
    """POST /login/ with valid credentials should redirect to / with session cookie"""

async def test_login_invalid_credentials():
    """POST /login/ with invalid credentials should redirect to /login with error message"""

async def test_logout():
    """GET /logout/ should clear session cookie and redirect to /login/"""

async def test_index_authenticated_redirects_to_location():
    """GET / as authenticated user should redirect to first location"""

async def test_index_unauthenticated_redirects_to_login():
    """GET / without session should redirect to /login/"""

async def test_location_overview_authenticated():
    """GET /{location_id}/ should render location page for authenticated user"""

async def test_location_overview_unauthenticated():
    """GET /{location_id}/ should redirect to login for unauthenticated user"""
```

**Effort:** Medium - Similar patterns exist in `test_auth_api.py`

---

### 2. Task Executor Tests (`heim/tasks/executor.py`)

**Why:** The task executor is the backbone of background processing. Bugs here could cause data loss or missed updates.

**Suggested tests:**
```python
# tests/test_task_executor.py

async def test_load_tasks_discovers_task_modules():
    """load_tasks() should import all tasks.py modules"""

async def test_run_next_task_executes_pending_task():
    """run_next_task() should execute and complete a pending task"""

async def test_run_next_task_returns_false_when_no_tasks():
    """run_next_task() should return False when no tasks are pending"""

async def test_execute_task_handles_failure():
    """Failed tasks should be marked as failed, not completed"""

async def test_execute_task_respects_timeout():
    """Tasks exceeding timeout should be cancelled"""

async def test_execute_task_atomic_uses_transaction():
    """Atomic tasks should run within a database transaction"""

async def test_execute_task_schedules_next_for_recurring():
    """Completed scheduled tasks should queue the next occurrence"""
```

**Effort:** Medium-High - Requires mocking task registry

---

### 3. YR Weather Client Tests (`heim/integrations/yr/client.py`)

**Why:** External API integration is a common source of bugs. Testing with mocked responses ensures reliability.

**Suggested tests:**
```python
# tests/yr/test_client.py

async def test_get_location_forecast_success():
    """Successful API call should return response with forecast data"""

async def test_get_location_forecast_with_if_modified_since():
    """If-Modified-Since header should be included when provided"""

async def test_get_location_forecast_truncates_coordinates():
    """Coordinates should be truncated to 4 decimal places"""

async def test_get_location_forecast_includes_user_agent():
    """User-Agent header should be set"""

async def test_get_location_forecast_handles_304():
    """304 Not Modified response should be handled correctly"""
```

**Effort:** Low - Simple function with httpx, use respx or httpx_mock

---

### 4. Aqara Client Tests (`heim/integrations/aqara/client.py`)

**Why:** The Aqara integration is critical for sensor data. The client has complex authentication logic.

**Suggested tests:**
```python
# tests/aqara/test_client.py

async def test_get_auth_code():
    """get_auth_code should return auth code from API"""

async def test_get_token():
    """get_token should return access and refresh tokens"""

async def test_refresh_token():
    """refresh_token should return new tokens"""

async def test_get_all_devices_paginates():
    """get_all_devices should handle pagination correctly"""

async def test_get_device_resources():
    """get_device_resources should return resource list"""

async def test_get_resource_history():
    """get_resource_history should return historical data"""

async def test_request_handles_expired_token():
    """ExpiredAccessToken should be raised when token expires (code 108)"""

async def test_request_handles_api_error():
    """AqaraAPIError should be raised for non-zero response codes"""

async def test_prepare_auth_generates_correct_signature():
    """Authentication signature should be correctly computed"""
```

**Effort:** Medium - Requires mocking httpx client

---

## Priority 2: Medium-Impact Test Additions

### 5. Forecast Queries Tests (`heim/forecasts/queries.py`)

**Why:** Forecast data is a key feature. These queries have complex SQL.

**Suggested tests:**
```python
# tests/test_forecast_queries.py

async def test_create_forecast():
    """create_forecast should insert and return forecast ID"""

async def test_create_forecast_instance():
    """create_forecast_instance should insert instance with values"""

async def test_create_forecast_instance_handles_conflict():
    """Duplicate forecast instance should be ignored (ON CONFLICT DO NOTHING)"""

async def test_get_forecast_coordinate():
    """get_forecast_coordinate should return location coordinate"""

async def test_get_forecast():
    """get_forecast should return forecast ID for account/location"""

async def test_get_instances():
    """get_instances should return latest, 12h, and 24h instances"""
```

**Effort:** Medium - Requires additional fixtures for forecasts

---

### 6. Aqara Services Tests (`heim/integrations/aqara/services.py`)

**Why:** The `with_aqara_client` decorator and token refresh logic are critical.

**Suggested tests:**
```python
# tests/aqara/test_services.py

async def test_with_aqara_client_injects_client():
    """Decorator should inject AqaraClient to decorated function"""

async def test_with_aqara_client_refreshes_on_expired_token():
    """Decorator should refresh token and retry on ExpiredAccessToken"""

async def test_refresh_access_token():
    """refresh_access_token should update stored tokens"""

async def test_refresh_access_token_fails_in_transaction():
    """refresh_access_token should raise if called within transaction"""
```

**Effort:** Medium - Requires careful mocking

---

### 7. Sensor Queries Tests (`heim/sensors/queries.py`)

**Why:** Simple but important - ensures measurements are saved correctly.

**Suggested tests:**
```python
# tests/test_sensor_queries.py

async def test_save_measurements():
    """save_measurements should insert all measurements"""

async def test_save_measurements_handles_conflict():
    """Duplicate measurements should be ignored"""
```

**Effort:** Low - Simple query with existing patterns

---

### 8. Forecasts API Tests (`heim/forecasts/api.py`)

**Why:** Ensures API endpoint works correctly with authentication.

**Suggested tests:**
```python
# tests/test_forecasts_api.py

async def test_get_forecasts_authenticated():
    """GET /locations/{id}/forecasts should return forecast data"""

async def test_get_forecasts_unauthenticated():
    """GET /locations/{id}/forecasts should return 401 without auth"""
```

**Effort:** Low - Similar to existing `test_locations_api.py`

---

## Priority 3: Lower-Impact but Valuable Tests

### 9. Task Base Tests (`heim/tasks/base.py`)

```python
# tests/test_task_base.py

def test_task_decorator_registers_task():
    """@task decorator should register task in registry"""

def test_get_task_returns_registered_task():
    """get_task should return task by name"""

def test_get_task_raises_for_unknown():
    """get_task should raise KeyError for unknown task"""

def test_task_call_returns_bound_task():
    """Calling a Task should return a BoundTask with bound arguments"""

async def test_bound_task_await():
    """Awaiting a BoundTask should execute the underlying function"""

async def test_bound_task_defer():
    """BoundTask.defer should queue task for execution"""

async def test_bound_task_schedule():
    """BoundTask.schedule should create scheduled task"""

def test_bound_task_warns_if_not_consumed():
    """BoundTask should warn if never awaited or scheduled"""
```

---

### 10. Utilities Tests (`heim/utils.py`)

Test any utility functions that have non-trivial logic.

---

## Testing Infrastructure Recommendations

### 1. Add HTTP Client Mocking

Install `respx` or use `pytest-httpx` for mocking external HTTP calls:

```toml
# pyproject.toml
[tool.poetry.dev-dependencies]
respx = "^0.20.0"  # or pytest-httpx = "^0.21.0"
```

### 2. Add Coverage Thresholds

Add minimum coverage thresholds to CI:

```toml
# pyproject.toml
[tool.coverage.report]
fail_under = 70  # Start with 70%, increase over time
```

### 3. Create Additional Fixtures

Add fixtures for commonly needed test entities:

```python
# tests/conftest.py

@pytest.fixture
async def forecast_id(location_id: int, account_id: int) -> int:
    return await create_forecast(
        name="Test forecast",
        account_id=account_id,
        location_id=location_id
    )

@pytest.fixture
async def sensor_id(location_id: int) -> int:
    # Create a sensor for testing
    ...
```

### 4. Add Integration Tests

Consider a separate test category for integration tests that:
- Test actual database migrations
- Test full task execution flows
- Test actual API responses (not just status codes)

---

## Recommended Implementation Order

1. **Week 1:** Frontend views tests, YR client tests (highest user impact)
2. **Week 2:** Task executor tests, Aqara client tests (highest reliability impact)
3. **Week 3:** Forecast queries, sensor queries, Aqara services (data integrity)
4. **Week 4:** Task base tests, API tests, utilities (completeness)

---

## Quick Wins (< 1 hour each)

1. Add `test_save_measurements` in `tests/test_sensor_queries.py`
2. Add `test_get_forecasts_authenticated` in `tests/test_forecasts_api.py`
3. Add `test_login_success` in `tests/test_frontend_views.py`
4. Add `test_get_location_forecast_success` in `tests/yr/test_client.py`

These four tests would immediately increase coverage of the critical paths with minimal effort.
