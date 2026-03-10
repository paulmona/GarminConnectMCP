# Plan: Add Oura Ring Support & Rename to Fitness MCP

## Decisions Made

- **Package rename**: `garmin_mcp` → `fitness_mcp`
- **Oura auth**: Full OAuth2 authorization code flow (server-side with refresh tokens)
- **Tool naming**: Source-prefixed for new Oura tools (e.g., `get_oura_sleep`); existing Garmin tools keep current names
- **Optionality**: Both sources fully optional — server works with only Garmin, only Oura, or both configured

---

## Phase 1: Package Rename (`garmin_mcp` → `fitness_mcp`)

This is the foundation — do it first before adding any new code.

### 1.1 Rename the Python package
- Rename `src/garmin_mcp/` → `src/fitness_mcp/`
- Update `pyproject.toml`:
  - `name = "fitness-mcp"` (or keep `garmin-connect-mcp` as the distribution name and just change the package)
  - `[project.scripts]` entry: keep `garmin-mcp` as an alias, add `fitness-mcp` entrypoint
  - Update `packages` path to `src/fitness_mcp`
- Update all internal imports: `from garmin_mcp.` → `from fitness_mcp.`
- Update `__init__.py`, `__main__.py`
- Update all test imports in `tests/`

### 1.2 Update Docker & CI
- Update `Dockerfile` references to the package
- Update `.github/workflows/ci.yml` and `docker.yml` if they reference `garmin_mcp`
- Update `docker-compose.yml` if present
- Consider keeping Docker image name `paulmon/garmin-connect-mcp` for now (breaking change for existing users) or adding a new image name

### 1.3 Update documentation
- Update `README.md` references
- Update `CLAUDE.md` references
- Update any inline comments referencing the old name

### 1.4 Verify
- Run `uv sync --extra dev` to ensure the renamed package installs
- Run `uv run pytest` — all 45+ existing tests must pass
- Run `uv run ruff check` and `uv run ruff format --check`

---

## Phase 2: Multi-Source Architecture

Introduce abstractions that make it natural to plug in new data sources.

### 2.1 Create a base client interface
```
src/fitness_mcp/clients/
├── __init__.py
├── base.py          # Abstract base / protocol for fitness clients
├── garmin.py        # Move garmin_client.py here (re-export from old location for compat)
└── oura.py          # New OuraClient (Phase 3)
```

**`base.py`** — defines the contract:
```python
from typing import TypeVar, Callable, Protocol

T = TypeVar("T")

class FitnessClient(Protocol):
    """Protocol for fitness data source clients."""
    def call_with_retry(self, fn: Callable[..., T]) -> T: ...
    def invalidate(self) -> None: ...
```

This is lightweight — not a heavy framework. Just enough to establish the pattern.

### 2.2 Refactor `garmin_client.py`
- Move to `src/fitness_mcp/clients/garmin.py`
- Keep `src/fitness_mcp/garmin_client.py` as a thin re-export for backward compatibility (or update all imports)
- `GarminClient` already matches the `FitnessClient` protocol — no changes to its implementation needed

### 2.3 Refactor config.py for multi-source
```python
@dataclass(frozen=True)
class GarminSettings:
    email: str
    password: str
    session_dir: Path

@dataclass(frozen=True)
class OuraSettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    token_dir: Path  # persisted OAuth tokens

@dataclass(frozen=True)
class Settings:
    garmin: GarminSettings | None  # None if GARMIN_EMAIL not set
    oura: OuraSettings | None      # None if OURA_CLIENT_ID not set

    @classmethod
    def load(cls) -> "Settings": ...
```

Key change: instead of raising `CredentialsNotConfiguredError` at load time, each source is `None` if not configured. Individual tools check their source's availability and return `NOT_CONFIGURED_MSG`.

### 2.4 Refactor server.py client singletons
```python
_garmin_client: GarminClient | None = None
_oura_client: OuraClient | None = None

def _get_garmin_client() -> GarminClient:
    """Raises CredentialsNotConfiguredError if Garmin not configured."""
    ...

def _get_oura_client() -> OuraClient:
    """Raises CredentialsNotConfiguredError if Oura not configured."""
    ...
```

Existing `_get_client()` becomes `_get_garmin_client()`. All existing tool registrations update their call from `_get_client()` to `_get_garmin_client()`.

### 2.5 Reorganize tools directory
```
src/fitness_mcp/tools/
├── __init__.py
├── garmin/
│   ├── __init__.py
│   ├── activities.py    # moved from tools/activities.py
│   ├── health.py        # moved from tools/health.py
│   ├── training.py      # moved from tools/training.py
│   ├── body.py          # moved from tools/body.py
│   └── workouts.py      # moved from tools/workouts.py
└── oura/
    ├── __init__.py
    ├── sleep.py
    ├── activity.py
    ├── readiness.py
    ├── health.py
    └── workouts.py
```

### 2.6 Verify
- All existing tests pass with the restructured code
- No functional changes — just moving files and updating imports

---

## Phase 3: Oura OAuth2 Client

### 3.1 Oura OAuth2 flow implementation

**Environment variables:**
| Variable | Required | Description |
|----------|----------|-------------|
| `OURA_CLIENT_ID` | Yes (for Oura) | OAuth2 client ID from Oura developer portal |
| `OURA_CLIENT_SECRET` | Yes (for Oura) | OAuth2 client secret |
| `OURA_REDIRECT_URI` | No (default `http://localhost:8000/oura/callback`) | OAuth2 redirect URI |
| `OURA_TOKEN_DIR` | No (default `config/.oura-session`) | Token persistence directory |

**`src/fitness_mcp/clients/oura.py`** — `OuraClient`:
- Uses `httpx` (already a dependency) for all API calls
- OAuth2 authorization code flow:
  1. Generate authorize URL → user visits in browser
  2. Handle callback at `/oura/callback` → exchange code for tokens
  3. Store access_token + refresh_token on disk (JSON file, owner-only permissions)
  4. Auto-refresh when access_token expires (24-hour expiry via auth code grant)
  5. Refresh tokens are **single-use** — each refresh returns a new refresh_token (must persist the new one)
- `call_with_retry()` pattern: try request → on 401 → refresh token → retry once
- Use `httpx` directly (already a dependency) rather than third-party Oura SDKs — the REST API is simple
- **Note**: Authorization goes to `cloud.ouraring.com`, API calls go to `api.ouraring.com`
- Rate limit awareness: 5000 requests per 5 minutes (generous, but add basic tracking)

**OAuth2 Scopes to request**: `email personal daily heartrate workout session spo2Daily`

**Key URLs:**
| Purpose | URL |
|---------|-----|
| Authorize | `https://cloud.ouraring.com/oauth/authorize` |
| Token | `https://api.ouraring.com/oauth/token` |
| Revoke | `https://api.ouraring.com/oauth/revoke` |
| API Base | `https://api.ouraring.com` |

### 3.2 Oura ASGI middleware for OAuth callback
Add a lightweight middleware/route to handle the Oura OAuth callback:
```
GET /oura/authorize  → redirects to Oura's authorize URL
GET /oura/callback   → handles the code exchange, stores tokens
GET /oura/status     → returns whether Oura is connected
```

This is separate from the MCP server's own OAuth (which gates access to the MCP). This is the Oura-as-data-source OAuth.

### 3.3 Alternative: CLI-based initial auth
For stdio mode (Claude Desktop), provide a one-time setup command:
```bash
fitness-mcp oura-auth
```
Opens browser, runs local callback server on a temp port, exchanges code, saves tokens. Similar to how `garth` handles Garmin auth.

### 3.4 Verify
- Unit tests for `OuraClient` (token refresh, retry logic, token persistence)
- Mock HTTP responses, don't hit real Oura API in tests

---

## Phase 4: Oura MCP Tools

### 4.1 Tool list (source-prefixed)

Based on the Oura API v2 endpoints, implement these tools:

| Tool Name | Oura Endpoint | Description |
|-----------|--------------|-------------|
| `get_oura_sleep` | `v2/usercollection/daily_sleep` | Daily sleep scores and contributor metrics |
| `get_oura_sleep_details` | `v2/usercollection/sleep` | Detailed sleep periods with HRV, movement, HR |
| `get_oura_sleep_time` | `v2/usercollection/sleep_time` | Optimal bedtime recommendations |
| `get_oura_readiness` | `v2/usercollection/daily_readiness` | Daily readiness scores with contributors |
| `get_oura_activity` | `v2/usercollection/daily_activity` | Activity scores, calories, steps, MET minutes |
| `get_oura_heart_rate` | `v2/usercollection/heartrate` | 5-minute interval heart rate time series |
| `get_oura_stress` | `v2/usercollection/daily_stress` | Daily stress and recovery minutes |
| `get_oura_spo2` | `v2/usercollection/daily_spo2` | Blood oxygen saturation (Gen 3+) |
| `get_oura_resilience` | `v2/usercollection/daily_resilience` | Daily resilience metrics |
| `get_oura_workouts` | `v2/usercollection/workout` | Workout data (type, calories, distance, duration) |
| `get_oura_cardiovascular_age` | `v2/usercollection/daily_cardiovascular_age` | Estimated cardiovascular age |
| `get_oura_vo2_max` | `v2/usercollection/vo2_max` | VO2 max estimates |
| `get_oura_personal_info` | `v2/usercollection/personal_info` | User profile (age, weight, height) |
| `get_oura_sessions` | `v2/usercollection/session` | Guided/unguided relaxation sessions |

**14 tools** — each follows the same pattern as existing Garmin tools.

### 4.2 Tool implementation pattern
Each tool in `server.py`:
```python
@mcp.tool()
def get_oura_sleep(days: int = 14) -> str:
    """Get Oura Ring daily sleep scores and contributors for the last N days."""
    days = _clamp_days(days)
    start_date, end_date = _date_range(days)
    try:
        result = _get_oura_client().call_with_retry(
            lambda api: get_sleep(api, start_date, end_date)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return OURA_NOT_CONFIGURED_MSG
```

Each tool module (e.g., `tools/oura/sleep.py`):
```python
def get_sleep(client: httpx.Client, start_date: str, end_date: str) -> list[dict]:
    """Fetch daily sleep data from Oura API."""
    resp = client.get("/v2/usercollection/daily_sleep", params={
        "start_date": start_date, "end_date": end_date
    })
    resp.raise_for_status()
    data = resp.json()["data"]
    return [_summarize_sleep(entry) for entry in data]
```

### 4.3 Shared utilities
- `_date_range(days)` already exists in health.py — extract to a shared `utils.py`
- `_validate_date()`, `_clamp_days()`, `_to_json()` — already in server.py, reusable as-is
- Add `OURA_NOT_CONFIGURED_MSG` alongside existing `NOT_CONFIGURED_MSG`

### 4.4 Verify
- Unit tests for each tool module in `tests/test_oura_*.py`
- Integration tests in `test_mcp_integration.py` — new `TestOuraTools` class
- Update tool count assertion (45 → 59)

---

## Phase 5: Testing & Documentation

### 5.1 Test files to add
```
tests/
├── test_oura_client.py           # OuraClient lifecycle, token refresh, retry
├── test_oura_sleep.py            # Sleep tool unit tests
├── test_oura_activity.py         # Activity tool unit tests
├── test_oura_readiness.py        # Readiness tool unit tests
├── test_oura_health.py           # HR, stress, SpO2, resilience tool tests
└── test_oura_workouts.py         # Workout tool unit tests
```

Plus additions to `test_mcp_integration.py` for all 14 Oura tools.

### 5.2 Documentation updates
- Update `README.md` with Oura setup instructions (OAuth flow, env vars)
- Update `CLAUDE.md` with new architecture, Oura tool list, env vars
- Add Oura section to Docker setup docs

### 5.3 CI updates
- No changes needed to CI workflows (they run pytest and linting generically)
- May need to add Oura test fixtures

---

## Phase 6: Future Multi-Source Enhancements (Out of Scope for Now)

These are noted for future reference but NOT part of this implementation:

- **Unified cross-source tools**: e.g., `get_recovery_overview()` pulling from both Garmin + Oura
- **Google Wear OS support**: Would follow same pattern (new client, new tools)
- **Whoop support**: Same pattern
- **Source comparison tools**: e.g., `compare_sleep_sources()` showing Garmin vs Oura sleep data side-by-side
- **Data normalization layer**: Common schema for sleep, HR, activity across sources

---

## Implementation Order

| Phase | Effort | Dependencies |
|-------|--------|-------------|
| Phase 1: Package rename | Medium | None |
| Phase 2: Multi-source architecture | Medium | Phase 1 |
| Phase 3: Oura OAuth2 client | Large | Phase 2 |
| Phase 4: Oura MCP tools | Large | Phase 3 |
| Phase 5: Testing & docs | Medium | Phase 4 |

Phases 1-2 can be shipped as a standalone PR (refactoring, no new features).
Phases 3-5 are the Oura feature PR.

---

## Environment Variables (Final State)

| Variable | Required | Description |
|----------|----------|-------------|
| `GARMIN_EMAIL` | For Garmin | Garmin Connect email |
| `GARMIN_PASSWORD` | For Garmin | Garmin Connect password |
| `GARMIN_SESSION_DIR` | No | Garmin token cache (default `config/.garmin-session`) |
| `OURA_CLIENT_ID` | For Oura | Oura OAuth2 client ID |
| `OURA_CLIENT_SECRET` | For Oura | Oura OAuth2 client secret |
| `OURA_REDIRECT_URI` | No | OAuth2 callback URI (default `http://localhost:8000/oura/callback`) |
| `OURA_TOKEN_DIR` | No | Oura token cache (default `config/.oura-session`) |
| `MCP_MODE` | No | `stdio` or `sse` |
| `MCP_API_KEY` | No | Bearer token for MCP auth |
| `MCP_SERVER_URL` | No | Public base URL |
| `MCP_TOTP_SECRET` | For OAuth | TOTP secret for authorize gate |
