# OAuth Approval Gate — Implementation Plan

## Problem

The `/authorize` endpoint auto-approves every OAuth request unconditionally.
Any claude.ai user who knows the server URL can complete the OAuth flow and
access Garmin data. The only step in the entire flow that involves a real
browser (and therefore a specific human) is the `/authorize` redirect — so
that is the correct place to add a user-identity check.

## Solution

Add `_OAuthApprovalMiddleware` that intercepts `GET /authorize` and shows an
HTML password form before passing the request on to the MCP SDK. After the
user enters the correct `OAUTH_APPROVAL_PASSWORD`, a 30-day HMAC-signed
cookie is set so the form only appears once a month.

### User-visible flow

1. User adds the MCP server in claude.ai and clicks Connect
2. Browser redirects to `https://garminmcp.spider.org/authorize?...`
3. **New:** Password form is shown — user enters `OAUTH_APPROVAL_PASSWORD`
4. Middleware validates, sets 30-day `HttpOnly` cookie, redirects back to
   the same `/authorize?...` URL
5. Second hit has valid cookie → passes through to MCP SDK → issues code
6. OAuth completes normally — never needs repeating for 30 days

Anyone else hitting `/authorize` is stuck at the password form permanently.

---

## New Environment Variable

| Variable | Required | Description |
|----------|----------|-------------|
| `OAUTH_APPROVAL_PASSWORD` | Recommended | Password shown to browser on `/authorize`. If unset, server logs a warning and auto-approves (existing behaviour). |

Add to Unraid template and docker-compose alongside `MCP_API_KEY`.

---

## Implementation

### 1. New imports (server.py)

```python
import hashlib
import hmac
import html as _html
from urllib.parse import unquote_plus
```

### 2. New class: `_OAuthApprovalMiddleware` (server.py)

Add after `_Fix401Middleware`, before `_BearerAuthMiddleware`.

```python
class _OAuthApprovalMiddleware:
    """Gate /authorize behind a password prompt.

    Intercepts GET /authorize — shows an HTML password form if no valid
    approval cookie is present.  After correct password entry, sets a
    30-day HMAC-signed HttpOnly cookie and redirects back to the original
    /authorize URL so the MCP SDK can issue the auth code normally.

    POST /authorize is handled here (form submission); all other paths and
    methods pass straight through.
    """

    _COOKIE_NAME = "mcp_approved"
    _COOKIE_MAX_AGE = 30 * 24 * 3600   # 30 days in seconds
    _BUCKET_SECS = 300                  # 5-minute HMAC time buckets
    _BUCKET_WINDOW = 2                  # accept current + 1 previous bucket

    def __init__(self, app, password: str) -> None:
        self._app = app
        self._password = password
        self._hmac_key = password.encode()

    # -- HMAC cookie helpers --------------------------------------------------

    def _make_token(self) -> str:
        ts = int(time.time()) // self._BUCKET_SECS
        return hmac.new(self._hmac_key, str(ts).encode(), hashlib.sha256).hexdigest()

    def _is_valid_token(self, token: str) -> bool:
        ts = int(time.time()) // self._BUCKET_SECS
        for t in range(ts - self._BUCKET_WINDOW + 1, ts + 1):
            expected = hmac.new(
                self._hmac_key, str(t).encode(), hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(token, expected):
                return True
        return False

    def _get_cookie(self, headers: dict) -> str | None:
        raw = headers.get(b"cookie", b"").decode("utf-8", errors="replace")
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k.strip() == self._COOKIE_NAME:
                return v.strip()
        return None

    # -- ASGI -----------------------------------------------------------------

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("path") != "/authorize":
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        method = scope.get("method", "")
        qs = scope.get("query_string", b"").decode()

        if method == "GET":
            cookie = self._get_cookie(headers)
            if cookie and self._is_valid_token(cookie):
                await self._app(scope, receive, send)
                return
            await self._show_form(send, qs, error=False)

        elif method == "POST":
            body = b""
            while True:
                msg = await receive()
                body += msg.get("body", b"")
                if not msg.get("more_body", False):
                    break
            params = {}
            for pair in body.decode("utf-8", errors="replace").split("&"):
                if "=" in pair:
                    k, _, v = pair.partition("=")
                    params[unquote_plus(k)] = unquote_plus(v)
            entered = params.get("pw", "")
            redirect_qs = params.get("qs", "")
            if hmac.compare_digest(entered.encode(), self._password.encode()):
                token = self._make_token()
                location = f"/authorize?{redirect_qs}" if redirect_qs else "/authorize"
                cookie_header = (
                    f"{self._COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; "
                    f"Path=/; Max-Age={self._COOKIE_MAX_AGE}"
                )
                await send({
                    "type": "http.response.start", "status": 302,
                    "headers": [
                        (b"location", location.encode()),
                        (b"set-cookie", cookie_header.encode()),
                        (b"content-length", b"0"),
                    ],
                })
                await send({"type": "http.response.body", "body": b"", "more_body": False})
            else:
                await self._show_form(send, redirect_qs, error=True)

        else:
            await self._app(scope, receive, send)

    async def _show_form(self, send, qs: str, error: bool) -> None:
        qs_safe = _html.escape(qs, quote=True)
        err_html = (
            '<p class="err">Incorrect password — try again.</p>' if error else ""
        )
        body = f"""<!DOCTYPE html>
<html lang="en"><head>
  <meta charset="utf-8">
  <title>Approve MCP Connection</title>
  <style>
    body{{font-family:system-ui,sans-serif;max-width:380px;margin:80px auto;padding:20px}}
    input[type=password]{{width:100%;padding:8px;margin:6px 0 14px;box-sizing:border-box;font-size:1rem}}
    button{{padding:9px 22px;background:#0066cc;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:1rem}}
    .err{{color:#c00}}
  </style>
</head><body>
  <h2>Approve Connection</h2>
  <p>Enter your approval password to allow this connection to your Garmin data.</p>
  {err_html}
  <form method="post" action="/authorize">
    <input type="password" name="pw" placeholder="Approval password" autofocus>
    <input type="hidden" name="qs" value="{qs_safe}">
    <button type="submit">Approve</button>
  </form>
</body></html>""".encode()
        await send({
            "type": "http.response.start", "status": 200,
            "headers": [
                (b"content-type", b"text/html; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body, "more_body": False})
```

### 3. Wire into middleware stack (server.py `main()`)

```python
# Before (inside the api_key branch):
app = _RequestLogMiddleware(
    _CORSMiddleware(
        _OAuthDiscoveryFixMiddleware(
            _TokenEndpointMiddleware(
                _AcceptHeaderMiddleware(
                    _Fix401Middleware(mcp.streamable_http_app())
                ),
                resource_url=server_url + "/mcp",
            )
        )
    )
)

# After:
approval_password = os.environ.get("OAUTH_APPROVAL_PASSWORD", "").strip()
if not approval_password:
    _logger.warning(
        "OAUTH_APPROVAL_PASSWORD not set — /authorize is open to any claude.ai user. "
        "Set this variable to restrict OAuth to a single authorised user."
    )

inner = mcp.streamable_http_app()
if approval_password:
    inner = _OAuthApprovalMiddleware(inner, approval_password)

app = _RequestLogMiddleware(
    _CORSMiddleware(
        _OAuthDiscoveryFixMiddleware(
            _TokenEndpointMiddleware(
                _AcceptHeaderMiddleware(
                    _Fix401Middleware(inner)
                ),
                resource_url=server_url + "/mcp",
            )
        )
    )
)
```

### 4. Update middleware stack diagram (CLAUDE.md)

```
_RequestLogMiddleware
  _CORSMiddleware
    _OAuthDiscoveryFixMiddleware
      _TokenEndpointMiddleware
        _AcceptHeaderMiddleware
          _Fix401Middleware
            _OAuthApprovalMiddleware  ← new (only present if OAUTH_APPROVAL_PASSWORD set)
              mcp.streamable_http_app()
```

### 5. Document new env var (CLAUDE.md and SECURITY.md)

Add `OAUTH_APPROVAL_PASSWORD` to the environment variables tables in both files.
Update SECURITY.md §3 to describe the approval gate.

### 6. Update test_mcp_oauth.py

The test script uses `redirect_uri=https://httpbin.org/get` and hits `/authorize`
directly. With the gate enabled it will get the HTML form instead of a 302.

Two options:
- **Preferred:** set `OAUTH_APPROVAL_PASSWORD` in a local `.env` and have the
  script skip the gate by hitting the server without the env var set (local test
  only, never deployed without the password)
- **Alternative:** add a `--no-gate` flag / env var that disables the middleware
  in test mode (adds complexity, not recommended)

Simplest for now: note in the test script header that it requires the server to
be running without `OAUTH_APPROVAL_PASSWORD` set, or run against a local instance.

---

## Files Changed

| File | Change |
|------|--------|
| `src/garmin_mcp/server.py` | Add imports, add `_OAuthApprovalMiddleware` class, update `main()` |
| `CLAUDE.md` | Update middleware diagram, add env var to table |
| `SECURITY.md` | Update §3 to describe approval gate, add env var to table |

---

## Deployment Steps

1. Implement changes, run tests: `uv run pytest`
2. Set `OAUTH_APPROVAL_PASSWORD` in Unraid template (strong password, store in password manager)
3. Commit and push to GitHub
4. Build and push Docker image:
   ```
   docker buildx build --platform linux/amd64 --push -t paulmon/garmin-connect-mcp:latest .
   ```
5. Pull new image on Unraid and restart container
6. Test: connect via claude.ai — password form should appear on the `/authorize` step

---

## Security Notes

- The HMAC cookie uses `hashlib.sha256` keyed on `OAUTH_APPROVAL_PASSWORD`
- Cookie is `HttpOnly` + `SameSite=Strict` — not accessible to JavaScript, not
  sent cross-site
- Cookie lasts 30 days — you enter the password once a month at most
- `hmac.compare_digest` used for password comparison — timing-safe
- The hidden `qs` field in the form is HTML-escaped to prevent XSS
- If `OAUTH_APPROVAL_PASSWORD` is unset the middleware is not added and the
  server warns loudly — existing behaviour preserved, no silent regression
