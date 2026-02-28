"""MCP server exposing Garmin Connect data for Hyrox training analysis."""

import json
import os
import re
from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import CredentialsNotConfiguredError
from .garmin_client import GarminClient

NOT_CONFIGURED_MSG = json.dumps({
    "error": "not_configured",
    "message": "Garmin credentials not configured. Set GARMIN_EMAIL and GARMIN_PASSWORD environment variables.",
})

mcp = FastMCP("garmin-mcp")

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


def main():
    """Start the MCP server.

    Transport is controlled by MCP_MODE:
    - stdio (default): for local Claude Desktop use
    - sse: for Docker / remote use; binds to MCP_HOST:MCP_PORT
    """
    mode = os.environ.get("MCP_MODE", "stdio")
    if mode == "sse":
        mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("MCP_PORT", "8000"))
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
