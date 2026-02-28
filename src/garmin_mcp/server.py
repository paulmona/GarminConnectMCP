"""MCP server exposing Garmin Connect data for Hyrox training analysis."""

import json
import logging
import os
import re
import secrets
import time
from datetime import date
from typing import Any

_logger = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP

from .config import CredentialsNotConfiguredError
from .garmin_client import GarminClient

NOT_CONFIGURED_MSG = json.dumps({
    "error": "not_configured",
    "message": "Garmin credentials not configured. Set GARMIN_EMAIL and GARMIN_PASSWORD environment variables.",
})

mcp = FastMCP("Garmin Connect MCP")

_client: GarminClient | None = None

# Input validation constants
_MAX_DAYS = 90
_MAX_ACTIVITIES = 50
_ACTIVITY_ID_RE = re.compile(r"^\d{1,20}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _get_client() -> GarminClient:
    global _client
    if _client is None:
        _client = GarminClient()
    return _client


def _to_json(data: Any) -> str:
    return json.dumps(data, default=str, indent=2)


def _clamp_days(days: int, max_val: int = _MAX_DAYS) -> int:
    """Clamp days to [1, max_val] range."""
    return max(1, min(days, max_val))


def _validate_date(d: str) -> str:
    """Validate and return a YYYY-MM-DD date string. Raises ValueError on bad input."""
    if not _DATE_RE.match(d):
        raise ValueError(f"Invalid date format: {d!r}. Expected YYYY-MM-DD.")
    date.fromisoformat(d)  # validates it is a real date
    return d


def _validate_activity_id(activity_id: str) -> str:
    """Validate activity_id is a numeric string. Prevents injection."""
    if not _ACTIVITY_ID_RE.match(activity_id):
        raise ValueError(f"Invalid activity_id: {activity_id!r}. Expected numeric ID.")
    return activity_id


# --- Activities tools ---


@mcp.tool()
def get_recent_activities(
    limit: int = 10,
    activity_type: str | None = None,
) -> str:
    """Get recent Garmin activities. Returns date, name, distance, duration,
    heart rate, and pace for each activity. Optionally filter by activity type
    (e.g. 'running', 'cycling', 'swimming'). Limit capped at 50."""
    from .tools.activities import get_recent_activities as _get

    limit = max(1, min(limit, _MAX_ACTIVITIES))
    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api, limit=limit, activity_type=activity_type)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


@mcp.tool()
def get_activity_detail(activity_id: str) -> str:
    """Get full detail for a single Garmin activity including lap splits
    and heart rate zone breakdown. Use an activity_id from get_recent_activities."""
    from .tools.activities import get_activity_detail as _get

    activity_id = _validate_activity_id(activity_id)
    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api, activity_id=activity_id)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


@mcp.tool()
def get_activities_in_range(
    start_date: str,
    end_date: str,
    activity_type: str | None = None,
) -> str:
    """Get Garmin activities between start_date and end_date (YYYY-MM-DD).
    Optionally filter by activity type."""
    from .tools.activities import get_activities_in_range as _get

    start_date = _validate_date(start_date)
    end_date = _validate_date(end_date)
    try:
        result = _get_client().call_with_retry(
            lambda api: _get(
                api,
                start_date=start_date,
                end_date=end_date,
                activity_type=activity_type,
            )
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


# --- Health tools ---


@mcp.tool()
def get_hrv_trend(days: int = 28) -> str:
    """Get Heart Rate Variability trend over recent days with 7-day rolling
    average. Useful for tracking recovery and training readiness. Max 90 days."""
    from .tools.health import get_hrv_trend as _get

    days = _clamp_days(days)
    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api, days=days)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


@mcp.tool()
def get_sleep_history(days: int = 14) -> str:
    """Get sleep data over recent days including sleep score, total duration,
    and time in each sleep stage (deep, light, REM, awake). Max 90 days."""
    from .tools.health import get_sleep_history as _get

    days = _clamp_days(days)
    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api, days=days)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


@mcp.tool()
def get_body_battery(days: int = 7) -> str:
    """Get Garmin Body Battery levels over recent days including daily
    highest, lowest, charged, and drained values. Max 90 days."""
    from .tools.health import get_body_battery as _get

    days = _clamp_days(days)
    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api, days=days)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


@mcp.tool()
def get_resting_hr_trend(days: int = 14) -> str:
    """Get resting heart rate trend over recent days. Useful for tracking
    cardiovascular fitness and recovery. Max 90 days."""
    from .tools.health import get_resting_hr_trend as _get

    days = _clamp_days(days)
    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api, days=days)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


# --- Training tools ---


@mcp.tool()
def get_training_status() -> str:
    """Get current Garmin training status including VO2 max, training load,
    readiness score, and recovery time."""
    from .tools.training import get_training_status as _get

    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


@mcp.tool()
def get_race_predictions() -> str:
    """Get predicted race finish times for common distances (5K, 10K,
    half marathon, marathon) based on your Garmin fitness data."""
    from .tools.training import get_race_predictions as _get

    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


@mcp.tool()
def get_weekly_summary(target_date: str | None = None) -> str:
    """Get a composite weekly summary: total activities, distance, duration,
    average resting HR, average sleep score. Defaults to current week.
    Provide target_date (YYYY-MM-DD) for a specific week."""
    from .tools.training import get_weekly_summary as _get

    if target_date is not None:
        target_date = _validate_date(target_date)
    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api, target_date=target_date)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


@mcp.tool()
def get_recovery_snapshot() -> str:
    """Use this tool first when asked about recovery, readiness, or whether to
    do a hard session. Returns all key recovery metrics in one call: HRV
    (last night value + status), sleep score + duration, current body battery
    level, yesterday's resting HR, and training readiness score."""
    from .tools.training import get_recovery_snapshot as _get

    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


# --- Body composition tools ---


@mcp.tool()
def get_weight_trend(days: int = 30) -> str:
    """Get weight trend over recent days including daily weights, BMI,
    and a summary of min/max/average/change. Max 90 days."""
    from .tools.body import get_weight_trend as _get

    days = _clamp_days(days)
    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api, days=days)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


@mcp.tool()
def get_body_composition(days: int = 30) -> str:
    """Get body composition trend over recent days including body fat %,
    muscle mass, bone mass, body water %, visceral fat, and metabolic age.
    Data only available if you use a Garmin smart scale. Max 90 days."""
    from .tools.body import get_body_composition as _get

    days = _clamp_days(days)
    try:
        result = _get_client().call_with_retry(
            lambda api: _get(api, days=days)
        )
        return _to_json(result)
    except CredentialsNotConfiguredError:
        return NOT_CONFIGURED_MSG


class _SimpleOAuthProvider:
    """Minimal in-memory OAuth 2.0 provider for personal use.

    Auto-approves every authorization request and issues MCP_API_KEY as the
    access token. All state is in memory and resets on container restart.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._clients: dict = {}
        self._auth_codes: dict = {}
        self._access_tokens: dict = {}  # token → scopes
        self._refresh_tokens: dict = {}

    async def get_client(self, client_id: str):
        return self._clients.get(client_id)

    async def register_client(self, client_info) -> None:
        self._clients[client_info.client_id] = client_info

    async def authorize(self, client, params) -> str:
        from mcp.server.auth.provider import AuthorizationCode, construct_redirect_uri
        code = secrets.token_urlsafe(32)
        self._auth_codes[code] = AuthorizationCode(
            code=code,
            scopes=params.scopes or [],
            expires_at=time.time() + 300,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(self, client, authorization_code: str):
        return self._auth_codes.get(authorization_code)

    async def exchange_authorization_code(self, client, authorization_code):
        from mcp.server.auth.provider import OAuthToken, RefreshToken
        del self._auth_codes[authorization_code.code]
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        self._access_tokens[access] = authorization_code.scopes
        self._refresh_tokens[refresh] = RefreshToken(
            token=refresh, client_id=client.client_id, scopes=authorization_code.scopes
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            scope=" ".join(authorization_code.scopes),
            refresh_token=refresh,
        )

    async def load_access_token(self, token: str):
        from mcp.server.auth.provider import AccessToken
        # Accept OAuth-issued tokens (fresh random tokens from exchange_authorization_code)
        scopes = self._access_tokens.get(token)
        if scopes is not None:
            _logger.info("load_access_token: OAuth token matched, scopes=%s", scopes)
            return AccessToken(token=token, client_id="oauth", scopes=scopes)
        # Also accept the raw API key for direct bearer token use (Claude Desktop etc.)
        if token == self._api_key:
            _logger.info("load_access_token: direct API key matched")
            return AccessToken(token=token, client_id="direct", scopes=["claudeai"])
        _logger.info("load_access_token: no match for token_len=%d", len(token))
        return None

    async def load_refresh_token(self, client, refresh_token: str):
        t = self._refresh_tokens.get(refresh_token)
        return t if t and t.client_id == client.client_id else None

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        from mcp.server.auth.provider import OAuthToken, RefreshToken
        del self._refresh_tokens[refresh_token.token]
        access = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)
        self._access_tokens[access] = refresh_token.scopes
        self._refresh_tokens[new_refresh] = RefreshToken(
            token=new_refresh, client_id=client.client_id, scopes=refresh_token.scopes
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            scope=" ".join(refresh_token.scopes),
            refresh_token=new_refresh,
        )

    async def revoke_token(self, token) -> None:
        from mcp.server.auth.provider import RefreshToken
        if isinstance(token, RefreshToken):
            self._refresh_tokens.pop(token.token, None)
        else:
            self._access_tokens.pop(getattr(token, "token", str(token)), None)

    async def verify_token(self, token: str):
        return await self.load_access_token(token)


class _AcceptHeaderMiddleware:
    """Normalize Accept headers before requests reach the MCP transport.

    The MCP streamable-http transport requires both application/json and
    text/event-stream in the Accept header. Some clients (e.g. claude.ai)
    send Accept: */* which the SDK doesn't recognise, causing 406 responses.
    This middleware replaces wildcards with the explicit types the SDK expects.
    """

    _REQUIRED = b"application/json, text/event-stream"

    def __init__(self, app) -> None:
        self._app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            headers = list(scope["headers"])
            idx = next((i for i, (k, _) in enumerate(headers) if k.lower() == b"accept"), None)
            if idx is None:
                headers.append((b"accept", self._REQUIRED))
            else:
                existing = headers[idx][1].decode()
                if "application/json" not in existing or "text/event-stream" not in existing:
                    headers[idx] = (b"accept", self._REQUIRED)
            scope = {**scope, "headers": headers}
        await self._app(scope, receive, send)


class _BearerAuthMiddleware:
    """Raw ASGI middleware that enforces Bearer token auth on all requests.

    Uses the raw ASGI interface (not BaseHTTPMiddleware) so SSE streaming
    is never buffered.
    """

    def __init__(self, app, api_key: str) -> None:
        self._app = app
        self._api_key = api_key

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode("utf-8", errors="replace")
            if auth != f"Bearer {self._api_key}":
                if scope["type"] == "http":
                    body = b"Unauthorized"
                    await send({
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"text/plain"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    })
                    await send({"type": "http.response.body", "body": body, "more_body": False})
                return
        await self._app(scope, receive, send)


def main():
    """Start the MCP server.

    Transport is controlled by MCP_MODE:
    - stdio (default): for local Claude Desktop use
    - sse: for Docker / remote use; binds to MCP_HOST:MCP_PORT

    When MCP_MODE=sse, set MCP_API_KEY to require Bearer token auth.
    """
    mode = os.environ.get("MCP_MODE", "stdio")
    if mode == "sse":
        from mcp.server.transport_security import TransportSecuritySettings
        mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("MCP_PORT", "8000"))
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )
        api_key = os.environ.get("MCP_API_KEY", "").strip()
        if api_key:
            import anyio
            import uvicorn
            from mcp.server.auth.provider import ProviderTokenVerifier
            from mcp.server.auth.settings import ClientRegistrationOptions
            from mcp.server.fastmcp.server import AuthSettings

            server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8000").rstrip("/")
            provider = _SimpleOAuthProvider(api_key)
            mcp._auth_server_provider = provider
            mcp._token_verifier = ProviderTokenVerifier(provider)
            mcp.settings.auth = AuthSettings(
                issuer_url=server_url,
                resource_server_url=server_url,
                client_registration_options=ClientRegistrationOptions(
                    enabled=True,
                    valid_scopes=["claudeai"],
                    default_scopes=["claudeai"],
                ),
            )

            async def _run() -> None:
                app = _AcceptHeaderMiddleware(mcp.streamable_http_app())
                config = uvicorn.Config(
                    app,
                    host=mcp.settings.host,
                    port=mcp.settings.port,
                    log_level=mcp.settings.log_level.lower(),
                )
                await uvicorn.Server(config).serve()

            anyio.run(_run)
        else:
            import anyio
            import uvicorn

            _logger.warning(
                "MCP_API_KEY not set — endpoint is unauthenticated. "
                "Set MCP_API_KEY to require Bearer token auth."
            )

            async def _run_open() -> None:
                app = _AcceptHeaderMiddleware(mcp.streamable_http_app())
                config = uvicorn.Config(
                    app,
                    host=mcp.settings.host,
                    port=mcp.settings.port,
                    log_level=mcp.settings.log_level.lower(),
                )
                await uvicorn.Server(config).serve()

            anyio.run(_run_open)
    else:
        mcp.run(transport="stdio")
