# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install all dependencies (including dev extras)
~/.local/bin/uv sync --extra dev

# Run all tests
~/.local/bin/uv run pytest

# Run a single test file
~/.local/bin/uv run pytest tests/test_server_startup.py

# Run a single test by name
~/.local/bin/uv run pytest tests/test_bearer_auth.py::TestBearerAuthMiddleware::test_valid_token_passes

# Run the server locally (stdio mode, for Claude Desktop)
GARMIN_EMAIL=x GARMIN_PASSWORD=y ~/.local/bin/uv run garmin-mcp

# Run the server in SSE/HTTP mode with OAuth
MCP_MODE=sse MCP_API_KEY=secret MCP_SERVER_URL=https://your-server.example.com \
  ~/.local/bin/uv run garmin-mcp

# End-to-end OAuth PKCE test against live server
~/.local/bin/uv run python3 test_mcp_oauth.py

# Build and run Docker container locally (for testing only — host arch)
docker compose up -d --build

# Build and push to Docker Hub for Unraid (must target linux/amd64 explicitly;
# building on Apple Silicon produces arm64 by default which won't run on Unraid)
docker buildx build --platform linux/amd64 --push -t paulmon/garmin-connect-mcp:latest .

# Release workflow (run these in order after making changes):
#   1. git add <files> && git commit -m "..."
#   2. git push origin main
#   3. Docker push happens automatically via GitHub Actions on merge to main
```

## Workflow

When working on a GitHub issue, always create a feature branch from `main` before making changes. Use the naming convention `feature/<short-description>` (e.g., `feature/totp-authorize-gate`). Commit messages and PR descriptions should include `Closes #<issue-number>` so the issue is automatically closed when the PR is merged.

### Bug workflow

When the user reports a bug and we confirm it exists:
1. **Create a GitHub issue** with the `bug` label — include symptoms, root cause, and expected behavior
2. **Create a fix branch** from `main` (e.g., `fix/<short-description>`)
3. **Comment on the issue** with progress updates as the fix is developed
4. **Include `Closes #<issue-number>`** in the PR description so the issue auto-closes on merge

## Architecture

The project is a single Python package (`src/garmin_mcp/`) built on [FastMCP](https://github.com/jlowin/fastmcp). All 13 MCP tools are registered on the global `mcp` instance in `server.py`.

### Transport modes

`main()` in `server.py` branches on `MCP_MODE`:

- **`stdio`** (default): used by Claude Desktop; `mcp.run(transport="stdio")`
- **`sse`**: used by Docker/remote; starts a uvicorn ASGI server on port 8000

When `MCP_MODE=sse` and `MCP_API_KEY` is set, the server also becomes a full OAuth 2.0 Authorization Server (for `claude.ai` remote MCP). When `MCP_API_KEY` is not set, it runs unauthenticated (localhost-only use case).

### ASGI middleware stack (outermost → innermost, OAuth mode)

```
_RequestLogMiddleware              # logs every REQ/RSP for debugging
  _CORSMiddleware                  # handles OPTIONS preflight, echoes claude.ai origin
    _OAuthDiscoveryFixMiddleware   # patches trailing-slash/auth-methods in discovery JSON
      _TokenEndpointMiddleware     # logs POST /token body + injects RFC 8707 resource field
        _AcceptHeaderMiddleware    # injects required Accept header if missing
          _Fix401Middleware        # strips error="invalid_token" from 401 WWW-Authenticate
            _TOTPGateMiddleware    # (when MCP_TOTP_SECRET set) requires 6-digit TOTP on /authorize
              mcp.streamable_http_app()  # FastMCP's ASGI app (POST /mcp endpoint)
```

### Key files

| File | Purpose |
|------|---------|
| `src/garmin_mcp/server.py` | All 13 tool definitions, `_SimpleOAuthProvider`, all ASGI middleware classes, `main()` entrypoint |
| `src/garmin_mcp/garmin_client.py` | `GarminClient` — wraps `garminconnect.Garmin`, handles session caching via garth tokens, `call_with_retry()` for mid-session re-auth |
| `src/garmin_mcp/config.py` | `Settings.load()` — reads `GARMIN_EMAIL`/`GARMIN_PASSWORD`/`GARMIN_SESSION_DIR` env vars; raises `CredentialsNotConfiguredError` if unset |
| `src/garmin_mcp/tools/activities.py` | `get_recent_activities`, `get_activity_detail`, `get_activities_in_range` |
| `src/garmin_mcp/tools/health.py` | `get_hrv_trend`, `get_sleep_history`, `get_body_battery`, `get_resting_hr_trend` |
| `src/garmin_mcp/tools/training.py` | `get_training_status`, `get_race_predictions`, `get_weekly_summary`, `get_recovery_snapshot` |
| `src/garmin_mcp/tools/body.py` | `get_weight_trend`, `get_body_composition` |
| `test_mcp_oauth.py` | Standalone E2E script: full OAuth PKCE flow → `POST /mcp`. Run directly with `uv run python3 test_mcp_oauth.py` |

### Tool pattern

Every tool in `server.py` follows this pattern:
1. Validate/clamp inputs (`_validate_date`, `_validate_activity_id`, `_clamp_days`)
2. Call `_get_client().call_with_retry(lambda api: _get(api, ...))` where `_get` is imported from the relevant `tools/` module
3. Return `_to_json(result)` or `NOT_CONFIGURED_MSG` on `CredentialsNotConfiguredError`

### OAuth / `_SimpleOAuthProvider`

Fully in-memory; all state is lost on container restart (tokens, registered clients). Issues random tokens via `secrets.token_urlsafe(32)` — not the API key itself. Also accepts `MCP_API_KEY` directly as a Bearer token so Claude Desktop and curl don't need to do OAuth.

### Input validation constants (server.py)

- `_MAX_DAYS = 90` — caps all `days` params
- `_MAX_ACTIVITIES = 50` — caps `limit` in `get_recent_activities`
- `_ACTIVITY_ID_RE` — numeric string, 1–20 digits
- `_DATE_RE` — `YYYY-MM-DD` followed by `date.fromisoformat()` validation

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GARMIN_EMAIL` | Yes | Garmin Connect email |
| `GARMIN_PASSWORD` | Yes | Garmin Connect password |
| `MCP_MODE` | No (default `stdio`) | `sse` for Docker/remote |
| `MCP_API_KEY` | No | Bearer token; enables OAuth server when set in SSE mode |
| `MCP_SERVER_URL` | No (default `http://localhost:8000`) | Public base URL for OAuth issuer/resource metadata |
| `MCP_TOTP_SECRET` | Yes (when `MCP_API_KEY` set) | Base32 TOTP secret; required for OAuth mode to prevent unauthorized token issuance |
| `MCP_ALLOWED_HOSTS` | No | Extra allowed Host headers (comma-separated); `MCP_SERVER_URL` hostname is always included |
| `MCP_DEBUG` | No | Set to `true` to log full OAuth token request/response bodies and Bearer token prefixes. Off by default to prevent secret leakage |
| `MCP_HOST` | No (default `0.0.0.0`) | SSE bind address |
| `MCP_PORT` | No (default `8000`) | SSE port |
| `MCP_ENDPOINT_PATH` | No (default `/mcp`) | Custom MCP endpoint path; use a random string (e.g. `/x7k9m2p4q8r1w3y5`) as an extra security layer |
| `GARMIN_SESSION_DIR` | No (default `config/.session`) | garth token cache directory |

## CI/CD (GitHub Actions)

Two workflows in `.github/workflows/`:

- **`ci.yml`** — runs on push to `main` and PRs to `main`. Jobs: `test` (pytest), `lint` (ruff check + format), `security` (bandit + pip-audit), `codeql` (GitHub code scanning).
- **`docker.yml`** — runs on push to `main` only. Re-runs tests, then builds `linux/amd64` image and pushes to `paulmon/garmin-connect-mcp:latest`.

Required GitHub secrets for Docker push: `DOCKERHUB_USERNAME` (`paulmon`), `DOCKERHUB_TOKEN`.

## Testing

Tests live in `tests/`. `pytest-asyncio` is configured with `asyncio_mode = "auto"`. Tests mock the Garmin API — no live credentials needed. The `test_mcp_oauth.py` script in the repo root requires a live server at `https://your-server.example.com` and is run manually, not via pytest.

### Integration tests (`tests/test_mcp_integration.py`)

**Every new MCP tool must have a corresponding integration test.** These tests exercise each tool through the full MCP Streamable HTTP protocol (JSON-RPC → FastMCP routing → tool function → mock API → JSON response). They catch issues that unit tests miss: wrong tool registration, MCP serialization problems, input schema mismatches.

When adding a new tool, add a test to the appropriate class in `test_mcp_integration.py`:
1. Set up mock return value on `mock_api` (the mocked `garminconnect.Garmin` instance)
2. Call `_call_tool(mcp_client, "tool_name", {"arg": "value"})`
3. Assert the parsed result contains expected fields
