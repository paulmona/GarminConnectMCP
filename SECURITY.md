# Security

Security model and hardening notes for GarminClaudeSync.

Last reviewed: 2026-02-27

---

## 1. Credential Storage

GarminClaudeSync needs a Garmin Connect email and password. These are stored
in **two places**, each with different sensitivity:

| Store | Contents | File permissions | In .gitignore |
|-------|----------|-----------------|---------------|
| `.env` | `GARMIN_EMAIL`, `GARMIN_PASSWORD` | 0600 (set on create via web UI) | Yes |
| `config.json` | HR zones, sync schedule, export prefs | 0600 (set by `save_config()`) | Yes |

**Credentials never appear in `config.json`.** The config store strips any
`garmin.*` keys on both load and save (`_FORBIDDEN_KEYS` in
`config_store.py`). This is a defense-in-depth measure in case application
code accidentally passes credentials into the config dict.

The `.env` file is the single source of truth for secrets. The web UI writes
to `.env` via `python-dotenv` `set_key()`. The MCP server reads from `.env`
via `Settings.from_env()`.

**Residual risk**: The password is stored as plaintext in `.env`. This is
standard for Python projects using `python-dotenv`, but on a shared machine
the file could be read by other users. For higher security, consider OS
keychain integration via the `keyring` library in a future release.

---

## 2. Session Tokens

Garmin OAuth tokens (managed by the `garth` library) are cached on disk to
avoid re-authentication on every server restart.

- **Location**: `.session/tokens` (configurable via `GARMIN_SESSION_DIR` env var)
- **Directory permissions**: `0700` (owner-only rwx), enforced by
  `os.chmod()` in `garmin_client.py` every time `_authenticate()` runs
- **TTL**: Garmin tokens typically expire after ~24 hours. The server
  handles this via `call_with_retry()`, which catches
  `GarminConnectAuthenticationError`, invalidates the cached client, and
  re-authenticates once before retrying the failed call
- **Fallback**: If the cached token store is invalid or corrupted, the
  client falls back to a fresh login with email/password credentials
- **Persistence failures**: If `garth.dump()` fails, a warning is logged
  but the server continues operating. The next restart will trigger a full
  re-authentication

The `.session/` directory is in `.gitignore` and must never be committed.

---

## 3. Web UI Security

The configuration web UI (`web/app.py`) is a FastAPI application that
provides a browser-based interface for editing non-secret settings (HR
zones, sync schedule, data export) and Garmin credentials.

### Binding

The server binds to `127.0.0.1:8585` (localhost only). It is not reachable
from other machines on the network. This is enforced in `start()` and should
never be changed to `0.0.0.0` without adding authentication.

### CSRF Protection

All POST endpoints validate a CSRF token before processing:

1. On every GET request, the server generates a per-session CSRF token
   (`secrets.token_hex(32)`) and stores it in memory keyed by session ID
2. The session ID is set as an `HttpOnly`, `SameSite=Strict` cookie
   (`gcs_session`)
3. Every HTML form includes a hidden `csrf_token` field
4. On POST, `_validate_csrf()` compares the form token against the session
   token using `secrets.compare_digest()` (timing-safe)
5. Mismatches return HTTP 403

This prevents cross-origin attacks (DNS rebinding, malicious pages targeting
localhost) from submitting forms to the web UI.

### Disabled Endpoints

OpenAPI (`/openapi.json`), Swagger UI (`/docs`), and ReDoc (`/redoc`) are
all disabled via `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`.
This prevents local processes from discovering endpoint structure.

### Input Validation

- Zone names: truncated to 10 characters
- BPM values: clamped to [0, 250]
- Sync interval: validated against allowlist `{15, 30, 60, 120, 360, 720, 1440}`
- Data export keys: validated against fixed allowlist

---

## 4. MCP Transport Modes

The server supports two transport modes, selected via the `MCP_MODE`
environment variable:

### stdio (default -- safe)

The server communicates over stdin/stdout with Claude Desktop as the parent
process. No network port is opened. Only Claude Desktop can send requests.
This is the recommended mode for local use.

### SSE (network -- requires caution)

Setting `MCP_MODE=sse` starts the server as an HTTP SSE endpoint. **This
mode currently has no authentication.** Any process that can reach the port
gets full read access to the user's Garmin health data.

**Production use of SSE mode requires an authentication layer.** Recommended
approach:

1. Set `MCP_API_KEY` in the environment with a strong random value
2. The server should require `Authorization: Bearer <MCP_API_KEY>` on all
   incoming SSE requests
3. If `MCP_MODE=sse` is set without `MCP_API_KEY`, the server should refuse
   to start

This is not yet implemented. **Do not expose SSE mode on a network without
adding authentication first.**

---

## 5. Input Validation

All MCP tool parameters are validated in `server.py` before being passed to
the Garmin API client:

| Parameter | Validation | Implementation |
|-----------|-----------|----------------|
| `activity_id` | Must match `^\d{1,20}$` | `_validate_activity_id()` |
| `start_date`, `end_date`, `target_date` | Must match `^\d{4}-\d{2}-\d{2}$` and be a valid calendar date (`date.fromisoformat()`) | `_validate_date()` |
| `days` (all health tools) | Clamped to [1, 90] | `_clamp_days()` |
| `limit` (get_recent_activities) | Clamped to [1, 50] | Inline `max/min` |
| Zone `min_bpm`, `max_bpm` (web UI) | Clamped to [0, 250] | Inline `max/min` |
| Zone `name` (web UI) | Truncated to 10 chars | `str()[:10]` |
| `interval_minutes` (web UI) | Allowlist: {15, 30, 60, 120, 360, 720, 1440} | Set membership check |

The `days` cap at 90 also serves as a rate-limit safety net. Without it,
`get_hrv_trend(days=10000)` would fire 10,000 sequential requests to
Garmin's servers, risking account lockout.

---

## 6. Known Limitations

### Garmin credentials are plaintext on disk

The `.env` file stores the Garmin password as plaintext. This is inherent to
the `python-dotenv` approach and consistent with standard Python project
conventions. Mitigation: `.env` is gitignored, and the web UI creates it
with `0600` permissions.

### MFA is not supported

The `garminconnect` library supports MFA via `prompt_mfa` and
`return_on_mfa` parameters, but GarminClaudeSync does not pass these. Users
with MFA enabled on their Garmin account will get an authentication error.
Garmin has been pushing MFA adoption, so this will affect a growing number
of users over time.

### Unofficial API

`garminconnect` reverse-engineers Garmin's web authentication. This is not
an official API. Garmin may break compatibility without notice. The
`call_with_retry` mechanism handles transient auth failures, but a
fundamental protocol change by Garmin will require a library update.

### Broad exception handling in tool modules

The tool modules (`health.py`, `activities.py`, `training.py`) use bare
`except Exception` blocks that catch all errors including auth failures and
rate limits. This means `call_with_retry` in `server.py` cannot re-auth on
mid-session token expiry within a day-by-day loop. A future improvement
should catch specific Garmin exception types and let auth errors propagate.

### Claude Desktop config contains plaintext password

The `claude_desktop_config.json` example in `docs/claude_desktop_setup.md`
includes the password in the `env` block. This is standard for MCP server
configuration, but users should be aware the file is stored at a well-known
path (`~/Library/Application Support/Claude/` on macOS).

---

## 7. For Contributors

### Do NOT:

- **Log credentials.** Never log `GARMIN_EMAIL` or `GARMIN_PASSWORD` at any
  level. The `Settings` dataclass is `frozen` and should not have a
  `__repr__` that exposes field values.

- **Commit `.env` or `.session/`.** Both are gitignored. If you see either
  in `git status`, something is wrong. Run `git rm --cached` immediately.

- **Store secrets in `config.json`.** Use `.env` for anything sensitive.
  The config store actively strips credential keys as a safety net, but
  do not rely on this -- never put secrets in the config dict.

- **Expose SSE mode without authentication.** The SSE transport opens a
  network port. Do not change the binding from `127.0.0.1` or remove the
  localhost restriction without implementing bearer token auth.

- **Disable CSRF validation.** Every POST endpoint in the web UI must call
  `_validate_csrf(request)`. Every HTML form must include the
  `csrf_token` hidden field.

- **Pass MCP tool inputs directly to API calls.** All user-supplied
  parameters (dates, IDs, counts) must be validated in `server.py` before
  reaching the Garmin client. Use the existing validation helpers.

- **Catch broad exceptions around Garmin API calls** without re-raising
  auth errors. `GarminConnectAuthenticationError` should propagate to
  `call_with_retry`. Only catch specific, expected exceptions.

### File permissions checklist

| Path | Expected | Enforced by |
|------|----------|-------------|
| `.env` | 0600 | `web/app.py` `Path.touch(mode=0o600)` |
| `.session/` | 0700 | `garmin_client.py` `os.chmod()` |
| `config.json` | 0600 | `config_store.py` `os.chmod()` |
