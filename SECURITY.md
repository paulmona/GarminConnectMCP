# Security Review: GarminClaudeSync

Reviewed: 2026-02-27
Reviewer: security (automated agent)
Scope: Full codebase as of Tasks #1-#8, #12 completion

---

## Executive Summary

GarminClaudeSync is an MCP server that authenticates to Garmin Connect using
username/password credentials and exposes health and fitness data to Claude
Desktop. The primary security concerns are **credential handling** (a
plaintext password stored on disk), **unauthenticated web UI** (a local HTTP
server that accepts credential-modifying POST requests without authentication
or CSRF protection), and **unvalidated MCP tool inputs** (parameters passed
directly to upstream API calls).

This review documents findings, severity ratings, and fixes applied.

---

## Findings

### SEC-01: Plaintext credentials in config.json [CRITICAL -- FIXED]

**File**: `src/garmin_mcp/web/config_store.py`
**Status**: Fixed in this review

The original `config_store.py` stored Garmin email and password in plaintext
in `config.json`. This file is written to the project working directory and
was at risk of accidental git commit.

**Fix applied**:
- Removed `garmin.email` and `garmin.password` from `DEFAULT_CONFIG`
- Added `_FORBIDDEN_KEYS` set that strips credential blocks on load and save
- `save_config()` now sanitizes output before writing
- `config.json` was already added to `.gitignore` (confirmed)

**Residual risk**: The web UI `POST /credentials` endpoint now writes to
`.env` via `python-dotenv` `set_key()`. The `.env` file is gitignored, but
the password is still stored as plaintext on disk. For a single-user local
tool this is acceptable. For higher security, consider OS keychain storage
via the `keyring` library.

---

### SEC-02: Web UI has no CSRF protection [HIGH -- FIXED]

**File**: `src/garmin_mcp/web/app.py`
**Status**: Fixed in this review

All POST endpoints (`/credentials`, `/hr-zones`, `/sync`, `/export`)
accepted form submissions without any CSRF token validation. Since the server
binds to `127.0.0.1:8585`, a malicious web page opened in the user's browser
could submit cross-origin POST requests to these endpoints, potentially
overwriting Garmin credentials in `.env`.

**Fix applied**:
- Added per-session CSRF token generation and validation
- All POST handlers now call `_validate_csrf(request)` before processing
- Session ID stored in `HttpOnly`, `SameSite=Strict` cookie
- CSRF token embedded as hidden field in all HTML forms
- Token comparison uses `secrets.compare_digest()` for timing-safe comparison

---

### SEC-03: Web UI exposes OpenAPI/Swagger docs [LOW -- FIXED]

**File**: `src/garmin_mcp/web/app.py`
**Status**: Fixed in this review

The FastAPI app exposed default `/docs`, `/redoc`, and `/openapi.json`
endpoints, which leak endpoint structure and parameter details to any local
process that can reach port 8585.

**Fix applied**: Disabled all OpenAPI endpoints via
`FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`.

---

### SEC-04: No MCP input validation [MEDIUM -- FIXED]

**File**: `src/garmin_mcp/server.py`
**Status**: Fixed in this review

MCP tool parameters were passed directly to Garmin API calls without
validation:

- `days` parameters had no upper bound. `get_hrv_trend(days=10000)` would
  fire 10,000 sequential HTTP requests, potentially triggering Garmin rate
  limits or account lockout.
- `activity_id` accepted arbitrary strings. While the garminconnect library
  likely URL-encodes them, defense-in-depth requires validating that
  activity IDs match the expected numeric format.
- `start_date` and `end_date` accepted arbitrary strings that could cause
  unexpected behavior in the Garmin API client.

**Fix applied**:
- `_clamp_days()`: All `days` parameters capped to [1, 90]
- `_validate_activity_id()`: Requires numeric string matching `^\d{1,20}$`
- `_validate_date()`: Requires YYYY-MM-DD format and valid calendar date
- `limit` parameter on `get_recent_activities` capped to [1, 50]

---

### SEC-05: Session token directory has default permissions [MEDIUM -- FIXED]

**File**: `src/garmin_mcp/garmin_client.py`
**Status**: Fixed in this review

The `.session/` directory (containing Garmin OAuth tokens) was created with
default filesystem permissions, meaning other users on a shared system could
read the tokens.

**Fix applied**: `os.chmod(token_dir, stat.S_IRWXU)` restricts the session
directory to owner-only access (mode 0700).

---

### SEC-06: .gitignore missing patterns [LOW -- FIXED]

**File**: `.gitignore`
**Status**: Fixed in this review

The original `.gitignore` covered `.env` and `.session/` but missed common
patterns that could leak secrets:

- `.env.*` variants (e.g., `.env.local`, `.env.production`)
- `.DS_Store` and `Thumbs.db` (OS metadata files)
- Generic `*.log` pattern

**Fix applied**: Added comprehensive ignore patterns with clear section
comments. `.env.example` is explicitly un-ignored so it remains tracked.

---

### SEC-07: SSE transport mode has no authentication [HIGH -- OPEN]

**File**: `src/garmin_mcp/server.py:184-191`
**Status**: Open -- requires design decision

The MCP server supports an `MCP_MODE=sse` environment variable that switches
from stdio to HTTP SSE transport. In SSE mode, the server listens on a
network port with **no authentication**. Any process that can reach the port
gets full read access to the user's Garmin health data.

While stdio mode (the default) is inherently secure because only the parent
process can communicate with the server, SSE mode should not be used without
authentication.

**Recommendation**:
1. Add a `MCP_API_KEY` environment variable. When SSE mode is enabled,
   require an `Authorization: Bearer <key>` header on all requests.
2. If `MCP_MODE=sse` is set without `MCP_API_KEY`, refuse to start and
   log an error explaining why.
3. Document this clearly in `docs/claude_desktop_setup.md`.

---

### SEC-08: Web UI credentials endpoint is unauthenticated [MEDIUM -- OPEN]

**File**: `src/garmin_mcp/web/app.py`
**Status**: Open -- mitigated by CSRF fix

The `POST /credentials` endpoint allows overwriting Garmin credentials in
`.env` without any user authentication. While CSRF protection (SEC-02 fix)
prevents cross-origin attacks, any local process or browser extension that
can make HTTP requests to `127.0.0.1:8585` can still modify credentials.

**Recommendation**: Consider one of:
1. Remove the credentials page entirely and document `.env` editing as the
   only way to set credentials (simplest, smallest attack surface).
2. Add a local authentication mechanism (e.g., a randomly generated admin
   token printed to stdout on server start, required as a query parameter
   or cookie to access the credentials page).

---

### SEC-09: Broad exception handling silences security errors [LOW -- OPEN]

**Files**: `src/garmin_mcp/tools/health.py`, `src/garmin_mcp/tools/activities.py`
**Status**: Open -- noted for future improvement

All API calls in the tool modules use bare `except Exception` blocks that
catch and silently discard all errors, including authentication failures and
rate-limit errors. This means:

- If a session token expires mid-request, the error is swallowed and `None`
  values are returned instead of triggering re-authentication.
- If Garmin rate-limits the client (HTTP 429), the tool continues firing
  requests rather than backing off.

**Recommendation**: Catch specific exception types. Let
`GarminConnectAuthenticationError` propagate so `call_with_retry` can
handle re-auth. Catch `GarminConnectTooManyRequestsError` separately and
implement backoff.

---

### SEC-10: Claude Desktop config example includes plaintext password [LOW -- OPEN]

**File**: `docs/claude_desktop_setup.md:37-39`
**Status**: Open -- documentation issue

The example `claude_desktop_config.json` includes the password as a
plaintext string in the `env` block. While this is typical for MCP server
configuration, users should be warned that this file is stored on disk in a
well-known location and may be readable by other applications.

**Recommendation**: Add a security note to the setup docs explaining:
- The config file contains your Garmin password in plaintext
- On macOS, the file is at `~/Library/Application Support/Claude/`
- Consider using a separate `.env` file and `dotenv` loading instead of
  inline env vars if your machine is shared

---

## Summary Table

| ID | Severity | Status | Description |
|----|----------|--------|-------------|
| SEC-01 | CRITICAL | Fixed | Plaintext password in config.json |
| SEC-02 | HIGH | Fixed | No CSRF protection on web UI |
| SEC-03 | LOW | Fixed | OpenAPI docs exposed |
| SEC-04 | MEDIUM | Fixed | No MCP input validation |
| SEC-05 | MEDIUM | Fixed | Session token dir permissions |
| SEC-06 | LOW | Fixed | Incomplete .gitignore |
| SEC-07 | HIGH | Open | SSE mode has no authentication |
| SEC-08 | MEDIUM | Open | Credentials endpoint unauthenticated |
| SEC-09 | LOW | Open | Broad exception handling |
| SEC-10 | LOW | Open | Docs show plaintext password |

**Fixed**: 6 findings
**Open**: 4 findings (none CRITICAL; 1 HIGH requires design decision)

---

## Files Modified in This Review

- `src/garmin_mcp/garmin_client.py` -- session dir permissions (SEC-05)
- `src/garmin_mcp/web/config_store.py` -- credential stripping (SEC-01)
- `src/garmin_mcp/web/app.py` -- CSRF protection, OpenAPI disabled (SEC-02, SEC-03)
- `src/garmin_mcp/web/templates/index.html` -- CSRF token hidden fields
- `src/garmin_mcp/server.py` -- input validation on all MCP tools (SEC-04)
- `.gitignore` -- additional sensitive file patterns (SEC-06)
- `SECURITY.md` -- this document (new file)
