# Security

Security model and hardening notes for Garmin Connect MCP Server.

Last reviewed: 2026-02-28

---

## 1. Credential Storage

Garmin credentials are passed **exclusively via environment variables** (`GARMIN_EMAIL`, `GARMIN_PASSWORD`). They are never written to disk by this server.

| Deployment | Where credentials live |
|------------|----------------------|
| Claude Desktop (stdio) | `claude_desktop_config.json` `env` block — stored at a well-known path (`~/Library/Application Support/Claude/` on macOS) |
| Docker | Container environment variables — set in Unraid template, `docker run -e`, or a `.env` file passed via `--env-file` |

**Residual risk**: In both cases the password is plaintext in a config file. On a shared machine this file could be read by other users. For higher security, consider OS keychain integration via the `keyring` library in a future release.

---

## 2. Session Tokens

Garmin OAuth tokens (managed by the `garth` library) are cached on disk to avoid re-authentication on every server restart.

- **Location**: `config/.session/` (configurable via `GARMIN_SESSION_DIR` env var); mounted as a named Docker volume in the container
- **Directory permissions**: `0700` (owner-only rwx), enforced by `os.chmod()` in `garmin_client.py` every time `_authenticate()` runs
- **TTL**: Garmin tokens typically expire after ~24 hours. The server handles this via `call_with_retry()`, which catches `GarminConnectAuthenticationError`, invalidates the cached client, and re-authenticates once before retrying the failed call
- **Persistence failures**: If `garth.dump()` fails, a warning is logged but the server continues operating. The next restart will trigger a full re-authentication

The session directory must never be committed to git (it is in `.gitignore`).

---

## 3. MCP Transport Modes

Transport is selected via the `MCP_MODE` environment variable:

### stdio (default — safe)

The server communicates over stdin/stdout with Claude Desktop as the parent process. No network port is opened. Only Claude Desktop can send requests. This is the recommended mode for local use.

### SSE / Streamable HTTP (network — requires `MCP_API_KEY`)

Setting `MCP_MODE=sse` starts the server as a Streamable HTTP endpoint on port 8000 (`POST /mcp`). When `MCP_API_KEY` is set the server enforces authentication on every request via one of two mechanisms:

1. **Direct Bearer token** — clients send `Authorization: Bearer <MCP_API_KEY>`. This is how Claude Desktop connects when pointing at a remote server.
2. **OAuth 2.0 PKCE** — a full OAuth 2.0 Authorization Server is exposed at the same base URL. Claude.ai uses this flow for remote MCP connections. Issued tokens are random (`secrets.token_urlsafe(32)`), short-lived in memory, and scoped to `claudeai`.

**Do not run SSE mode without `MCP_API_KEY`** when the port is reachable from the network. Without it, any process that can reach port 8000 gets full read access to the user's Garmin health data.

### TOTP gate (mandatory for OAuth mode)

When `MCP_API_KEY` is set, `MCP_TOTP_SECRET` **must** also be set — the server refuses to start without it. This prevents an authentication bypass where anyone could complete the OAuth flow (register → authorize → token → /mcp) without any credentials.

The `_TOTPGateMiddleware` intercepts `GET /authorize` and renders an HTML form requiring a 6-digit TOTP code from an authenticator app (Google Authenticator, Authy, etc.). Only after entering a valid code does the OAuth authorization proceed.

**Setup:**
1. Generate a TOTP secret: `python3 -c "import pyotp; print(pyotp.random_base32())"`
2. Set `MCP_TOTP_SECRET` to the generated value in your container environment
3. Add the secret to your authenticator app (manual entry, base32 key)

Without `/authorize` gated by TOTP, the OAuth provider auto-approves all requests — meaning anyone who discovers the server URL gets full access to all Garmin health data via the OAuth flow.

### DNS rebinding protection

When `MCP_API_KEY` is set, the server enables the MCP SDK's DNS rebinding protection. This validates the `Host` header on incoming requests, rejecting any that don't match an allowed hostname. The allowed hostname is automatically derived from `MCP_SERVER_URL`.

To allow additional hosts (e.g., LAN IPs for direct access), set `MCP_ALLOWED_HOSTS` to a comma-separated list:
```
MCP_ALLOWED_HOSTS=192.168.1.100,myserver.local
```

When `MCP_API_KEY` is **not** set (unauthenticated dev mode), DNS rebinding protection is disabled to allow localhost access without configuration.

---

## 4. Input Validation

All MCP tool parameters are validated in `server.py` before being passed to the Garmin API client:

| Parameter | Validation | Implementation |
|-----------|-----------|----------------|
| `activity_id` | Must match `^\d{1,20}$` | `_validate_activity_id()` |
| `start_date`, `end_date`, `target_date` | Must match `^\d{4}-\d{2}-\d{2}$` and be a valid calendar date | `_validate_date()` |
| `days` (all health tools) | Clamped to [1, 90] | `_clamp_days()` |
| `limit` (get_recent_activities) | Clamped to [1, 50] | Inline `max/min` |

The `days` cap at 90 also serves as a rate-limit safety net. Without it, `get_hrv_trend(days=10000)` would fire 10,000 sequential requests to Garmin's servers, risking account lockout.

---

## 5. Log Redaction (`MCP_DEBUG`)

By default, the ASGI middleware stack **redacts** sensitive material from logs:

| Middleware | Default (safe) | `MCP_DEBUG=true` |
|-----------|---------------|-----------------|
| `_RequestLogMiddleware` | `auth=Bearer ***` | `auth=Bearer <first 10 chars>...` |
| `_TokenEndpointMiddleware` (request) | Body length only | Full POST body (grant_type, code, etc.) |
| `_TokenEndpointMiddleware` (response) | `token_type` + `scope` + length | Full JSON including `access_token` and `refresh_token` |

Set `MCP_DEBUG=true` **only** when actively troubleshooting OAuth flows. Never leave it enabled in production — token values in logs can be used to impersonate users.

---

## 6. Known Limitations

### MFA is not supported

The `garminconnect` library supports MFA via `prompt_mfa` and `return_on_mfa` parameters, but this server does not pass these. Users with MFA enabled on their Garmin account will get an authentication error. Garmin has been pushing MFA adoption, so this will affect a growing number of users over time.

### Unofficial API

`garminconnect` reverse-engineers Garmin's web authentication. This is not an official API. Garmin may break compatibility without notice. The `call_with_retry` mechanism handles transient auth failures, but a fundamental protocol change by Garmin will require a library update.

### OAuth tokens are in-memory only

The OAuth 2.0 provider (`_SimpleOAuthProvider`) stores issued tokens in a Python dict. All tokens are lost on container restart, requiring clients (e.g. claude.ai) to re-authenticate. There is no persistent token store.

### Broad exception handling in tool modules

The tool modules (`health.py`, `activities.py`, `training.py`) use bare `except Exception` blocks that catch all errors including auth failures and rate limits. This means `call_with_retry` in `server.py` cannot re-auth on mid-session token expiry within a day-by-day loop. A future improvement should catch specific Garmin exception types and let auth errors propagate.

---

## 7. For Contributors

### Do NOT:

- **Log credentials.** Never log `GARMIN_EMAIL` or `GARMIN_PASSWORD` at any level.

- **Commit `.session/` or credential files.** The session directory is gitignored. If you see it in `git status`, run `git rm --cached` immediately.

- **Run SSE mode without `MCP_API_KEY` on a network port.** The transport opens port 8000 with no auth if the key is absent.

- **Pass MCP tool inputs directly to API calls.** All user-supplied parameters (dates, IDs, counts) must be validated in `server.py` before reaching the Garmin client. Use the existing validation helpers (`_validate_date`, `_validate_activity_id`, `_clamp_days`).

- **Catch broad exceptions around Garmin API calls** without re-raising auth errors. `GarminConnectAuthenticationError` should propagate to `call_with_retry`. Only catch specific, expected exceptions.

### File permissions checklist

| Path | Expected | Enforced by |
|------|----------|-------------|
| `config/.session/` | 0700 | `garmin_client.py` `os.chmod()` |
