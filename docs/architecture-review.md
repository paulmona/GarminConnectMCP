# Architecture Review: GarminClaudeSync

Devil's advocate review of design decisions, resilience gaps, and security
concerns. Each section contains a CONCERN and a RECOMMENDATION.

---

## 1. Garmin Auth Fragility

### CONCERN

The entire project depends on `python-garminconnect`, which reverse-engineers
Garmin's web authentication. This is not an official API. Garmin has no
obligation to maintain compatibility, and historically has broken third-party
integrations without notice.

Specific issues in `garmin_client.py`:

- **No mid-session re-auth.** The `api` property creates a client once and
  caches it forever in `self._client`. If a session expires during a long
  Claude conversation (Garmin tokens typically expire after ~24 hours), every
  subsequent API call will fail with no automatic recovery. The retry logic in
  `_authenticate()` only runs at initial login time, not when a cached session
  goes stale.

- **MFA is unsupported.** The `Garmin()` constructor accepts `prompt_mfa` and
  `return_on_mfa` parameters, but `GarminClient` passes neither. Users with
  MFA enabled on their Garmin account will get an authentication error with no
  helpful guidance. Since Garmin has been pushing MFA adoption, this will
  affect a growing number of users.

- **Silent token save failures.** `_save_tokens` catches all exceptions and
  logs a warning. If token persistence silently fails, every server restart
  will trigger a full re-authentication against Garmin's servers, increasing
  the chance of rate limiting or account lockout.

### RECOMMENDATION

1. Add a `with_retry` wrapper around API calls that catches
   `GarminConnectAuthenticationError`, sets `self._client = None`, re-authenticates
   once, and retries the call. This is the single most important fix.

2. Document MFA as unsupported in README and raise a clear error message if
   MFA is detected (the library raises a specific error for this). Long-term,
   consider supporting the `return_on_mfa` flow via the web config UI.

3. Make token save failures raise (or at least log at ERROR level) so operators
   notice persistent storage issues before they cascade.

---

## 2. Rate Limiting / API Abuse

### CONCERN

The health tools make O(N) API calls per invocation where N is the number of
days requested:

| Tool               | Default days | API calls per invocation |
|--------------------|-------------|-------------------------|
| `get_hrv_trend`    | 28          | 28                      |
| `get_sleep_history`| 14          | 14                      |
| `get_resting_hr_trend` | 14     | 14                      |
| `get_body_battery` | 7           | 1 (uses range endpoint) |

If Claude calls `get_hrv_trend(days=90)`, that fires 90 sequential HTTP
requests to Garmin's servers. Garmin's undocumented rate limits are reportedly
around 10-20 requests per minute for unofficial clients. This means:

- A single `get_hrv_trend(90)` call will take several minutes and may trigger
  a `GarminConnectTooManyRequestsError` (HTTP 429) partway through, returning
  partial data with no indication of truncation.

- Claude is likely to call multiple health tools in sequence ("show me my HRV,
  sleep, and resting HR trends"). That is 28 + 14 + 14 = 56 API calls in
  rapid succession.

- There is no inter-request delay, no backoff, and no per-session rate limiter.

- Repeated 429s or aggressive scraping patterns could trigger a temporary or
  permanent account lockout from Garmin Connect. Since this uses the user's
  real Garmin credentials, that means losing access to Garmin Connect entirely.

### RECOMMENDATION

1. **Add a local SQLite cache.** Cache API responses keyed by (endpoint, date)
   with a TTL of ~6 hours. Health data for past dates is immutable; once you
   have sleep data for 2024-02-15, it will never change. This eliminates
   redundant API calls across conversations and tool invocations. Only
   today's data needs freshness.

2. **Add a client-side rate limiter.** A simple `asyncio.Semaphore` or token
   bucket limiting to ~5 requests/second with exponential backoff on 429s.
   This is trivially implementable and prevents account lockout.

3. **Cap the `days` parameter.** The MCP tool schema should enforce a maximum
   (e.g., 90 days for HRV, 30 for sleep). Claude does not need 365 days of
   raw daily data to analyze training trends -- and if it does, the data
   should be pre-aggregated.

4. **Use batch/range endpoints where available.** `get_body_battery` already
   uses a date range endpoint (1 call for N days). Investigate whether
   similar range endpoints exist for sleep, HRV, and RHR. The
   `garminconnect` library may wrap them.

---

## 3. MCP Tool Granularity

### CONCERN

The planned tool set (based on task descriptions and implemented code) appears
to be approximately 8 tools:

1. `get_recent_activities` -- list activities
2. `get_activity_detail` -- single activity deep-dive
3. `get_activities_in_range` -- activities by date range
4. `get_hrv_trend` -- HRV over N days
5. `get_sleep_history` -- sleep over N days
6. `get_body_battery` -- body battery over N days
7. `get_resting_hr_trend` -- RHR over N days
8. (Planned) Training readiness/status

From a Claude usability perspective:

- **The health tools are too fragmented.** When a user asks "How recovered am
  I today?", Claude needs to call 4 separate tools (HRV, sleep, body battery,
  RHR), wait for each to return, then synthesize. Each tool independently
  loops over dates and hits Garmin's API. A single `get_daily_snapshot`
  tool that returns today's HRV + sleep + body battery + RHR + training
  readiness in one call would be faster, cheaper on API calls, and easier
  for Claude to work with.

- **No training readiness tool yet.** This is the most important metric for
  Hyrox training analysis (the stated purpose of the project), and it is
  listed as pending (Task #6).

- **Tool descriptions matter enormously.** Claude selects tools based on their
  docstrings. The current function docstrings are terse ("Get HRV trend over
  recent days with 7-day rolling average"). They should explicitly state what
  Hyrox-relevant insights the data enables, so Claude knows when to reach for
  each tool.

### RECOMMENDATION

1. Add a composite `get_recovery_snapshot` tool that fetches today's key
   recovery metrics in a single call. This is the tool Claude will use most.

2. Ensure every MCP tool has a rich description explaining: what data it
   returns, what training questions it helps answer, and when Claude should
   prefer it over other tools.

3. Consider adding a `get_training_load_summary` tool that combines recent
   activity volume (km, duration, TSS-equivalent) with recovery metrics,
   since Hyrox training analysis fundamentally needs both sides.

---

## 4. Data Volume and Token Cost

### CONCERN

MCP tools return data that goes into Claude's context window, which has token
limits and per-token costs. Current tool responses are unbounded:

- `get_hrv_trend(days=90)` returns 90 daily records, each with ~8 fields.
  That is roughly 3,000-4,000 tokens of raw JSON.

- `get_activities_in_range` over a month of Hyrox training could return 20-30
  activities, each with ~11 fields, plus laps and HR zones for detailed views.

- There is no summarization layer between the raw Garmin API response and what
  Claude sees. Claude gets a wall of JSON and has to extract patterns itself.

This is both expensive (more input tokens = higher cost) and degrades Claude's
analytical quality (important signals get lost in noise).

### RECOMMENDATION

1. Add server-side summarization for trend tools. Instead of returning 90 raw
   daily HRV records, return: current value, 7-day average, 28-day average,
   trend direction (improving/declining/stable), and notable anomalies. If
   Claude needs the raw daily data, it can request it explicitly.

2. Cap default `days` parameters to sensible defaults (28 for HRV, 14 for
   sleep, 7 for body battery) and document why.

3. For activity lists, return summaries by default and provide
   `get_activity_detail` for deep dives. This pattern is already implemented
   -- good.

---

## 5. Web Config UI Security

### CONCERN

The web configuration UI (`web/app.py`) has significant security issues:

- **Credentials stored in plaintext JSON.** `config_store.py` saves the
  Garmin password as plaintext in `config.json`. Anyone with filesystem
  access can read it. (The file is in `.gitignore`, so it won't be
  committed accidentally, but it is still plaintext on disk.)

- **No authentication on the web UI.** The FastAPI app on port 8585 has no
  login, no session management, no CSRF protection. Anyone who can reach
  the port can read and overwrite Garmin credentials.

- **Listening on 127.0.0.1 is not sufficient protection.** While the server
  binds to localhost, browser-based attacks (DNS rebinding, CSRF from a
  malicious page) can target localhost services. The web UI accepts POST
  requests with `Form()` data, which is trivially exploitable via CSRF since
  there is no token validation.

- **`config.json` is in `.gitignore`**, which prevents accidental commits.
  However, plaintext credentials on disk remain a risk if the machine is
  compromised or if backups capture the file.

### RECOMMENDATION

1. **Never store the password in config.json.** Store it only in `.env` or in
   the OS keychain. The web UI should write to `.env`, not to a JSON file.
   (`config.json` is already gitignored, which is good, but plaintext on disk
   is still a risk.)

2. **Add CSRF protection** to the web UI. FastAPI does not include CSRF
   middleware by default; use `starlette-csrf` or embed a hidden token.

3. **Consider whether the web UI is needed at all.** The current functionality
   (enter email/password, set HR zones, configure sync) could be handled
   entirely through `.env` variables and a one-time CLI setup command. A web
   UI increases attack surface for minimal UX gain in a developer-oriented
   tool.

---

## 6. MCP Transport Security

### CONCERN

The MCP server transport choice has not been implemented yet (Task #8), but
the decision has major security implications:

- **SSE transport (HTTP server)** means the MCP server listens on a port.
  If exposed beyond localhost, anyone with the URL gets full read access to
  the user's Garmin health data. The MCP SDK's `TransportSecuritySettings`
  provides DNS rebinding protection but is **disabled by default**.

- **stdio transport** (Claude Desktop's native approach) is inherently
  safer: only the parent process (Claude Desktop) can communicate with the
  server. No network port, no remote access risk.

- If SSE is chosen for remote/cloud use cases, there is no authentication
  mechanism in the MCP protocol itself. The server would need a custom auth
  middleware layer.

### RECOMMENDATION

1. **Default to stdio transport** for Claude Desktop integration. This is
   simpler and inherently secure.

2. If SSE is needed (e.g., for remote Claude API access), require an API key
   in an `Authorization` header, configurable via `MCP_API_KEY` env var.
   Enable `TransportSecuritySettings` with explicit `allowed_hosts`.

3. Document the security implications of each transport choice in README.

---

## 7. Error Propagation to Claude

### CONCERN

When Garmin API calls fail, the current tools silently swallow exceptions
and return empty/null data:

```python
# health.py pattern repeated in every tool:
except Exception:
    daily_values.append({"date": d, "weekly_avg": None})
```

This means Claude receives a response that looks successful but contains
gaps. Claude has no way to know whether null HRV data means "the user didn't
wear their watch" or "Garmin's servers are down" or "the session expired."

The `activities.py` tool functions also have bare `except Exception` blocks
around splits and HR zones fetches.

### RECOMMENDATION

1. Distinguish between "no data available" and "API error." Return a
   structured error field, e.g.:
   ```json
   {"date": "2024-02-15", "weekly_avg": null, "error": "auth_expired"}
   ```
   or raise a tool-level error that Claude can report to the user.

2. If multiple API calls fail in sequence (e.g., 5+ consecutive failures in
   a date range loop), abort early and return an error message rather than
   silently returning 28 null records.

3. Define a clear error taxonomy: `auth_expired`, `rate_limited`,
   `garmin_unavailable`, `no_data`. Map Garmin exceptions to these.

---

## 8. Credential Duplication

### CONCERN

There are now two places credentials can be stored:

1. `.env` file (read by `config.py` via `Settings.from_env()`)
2. `config.json` (written by the web UI via `config_store.py`)

These are not connected. The MCP server reads from `.env`, the web UI
reads/writes `config.json`. If a user sets credentials via the web UI, the
MCP server will not see them. If they set credentials in `.env`, the web UI
will show them as blank.

### RECOMMENDATION

1. Pick one source of truth. Given that this is a developer tool meant to be
   open-sourced, `.env` is the right choice. It is the standard for secrets
   in Python projects, works with `python-dotenv`, and is already in
   `.gitignore`.

2. If the web UI needs to set credentials, it should write to `.env` (or
   better: prompt once and store in the OS keychain via `keyring`).

3. Remove the `garmin.email` and `garmin.password` fields from
   `config_store.py`'s `DEFAULT_CONFIG`. Configuration that is not secret
   (HR zones, sync interval, export preferences) can stay in `config.json`.

---

## 9. Google Drive Fallback Fragility

### CONCERN

Task #9 plans a "Google Drive fallback sync script." The architectural
intent is unclear:

- Is this for syncing Garmin data to Google Drive as a backup?
- Or for reading from Google Drive when the Garmin API is unavailable?
- Google Drive API requires OAuth2 with its own auth flow, token refresh,
  and scopes. This is a significant addition to the project's auth surface.

### RECOMMENDATION

1. Clarify the use case before implementation. If the goal is simply to
   export Garmin data to a file Claude can read, a local JSON/CSV export
   would be simpler and involve zero additional auth complexity.

2. If Google Drive is needed, use a dedicated service account rather than
   user OAuth2 to avoid a second interactive auth flow.

---

## 10. Dependency Risk

### CONCERN

The project's core dependency chain is narrow and fragile:

- `garminconnect` -- maintained by a single developer, reverse-engineers
  an unofficial API. If Garmin changes their auth flow (they use Garth for
  OAuth), the library could break for days or weeks until patched.

- `mcp>=1.0.0` -- the MCP SDK is still young and evolving. Breaking changes
  between versions are possible.

- No pinned versions beyond minimums in `pyproject.toml`. `uv.lock` pins
  them, but a fresh `uv sync` without the lockfile could pull breaking
  versions.

### RECOMMENDATION

1. Pin `garminconnect` to a specific minor version (e.g., `>=0.2.25,<0.3`).
   Test before upgrading.

2. Add a health check endpoint or CLI command that validates the full
   dependency chain works: can authenticate to Garmin, can fetch one day of
   data, MCP server starts.

3. Document the "what to do when Garmin auth breaks" playbook for users, since
   this **will** happen eventually.

---

## Summary: Blocking Concerns

The following issues should be addressed before the project is open-sourced:

| Priority | Issue | Blocks |
|----------|-------|--------|
| **P0** | No mid-session re-auth (#1) | Task #18 |
| **P0** | Password stored in plaintext JSON (#5) | Task #19 |
| **P1** | No rate limiting on Garmin API calls (#2) | Health/training tools |
| **P1** | Credential source of truth conflict (#8) | Task #19 |
| **P1** | Silent error swallowing (#7) | All MCP tools |
| **P2** | MCP transport security defaults (#6) | Task #8 |
| **P2** | Tool granularity for Claude usability (#3) | Task #20 |
| **P2** | Data volume / token cost (#4) | Post-MVP |
