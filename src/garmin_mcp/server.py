"""MCP server exposing Garmin Connect data for Hyrox training analysis."""

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .garmin_client import GarminClient

mcp = FastMCP("garmin-mcp")

_client: GarminClient | None = None


def _get_client() -> GarminClient:
    global _client
    if _client is None:
        _client = GarminClient()
    return _client


def _to_json(data: Any) -> str:
    return json.dumps(data, default=str, indent=2)


# --- Activities tools ---


@mcp.tool()
def get_recent_activities(
    limit: int = 10,
    activity_type: str | None = None,
) -> str:
    """Get recent Garmin activities. Returns date, name, distance, duration,
    heart rate, and pace for each activity. Optionally filter by activity type
    (e.g. 'running', 'cycling', 'swimming')."""
    from .tools.activities import get_recent_activities as _get

    result = _get(_get_client().api, limit=limit, activity_type=activity_type)
    return _to_json(result)


@mcp.tool()
def get_activity_detail(activity_id: str) -> str:
    """Get full detail for a single Garmin activity including lap splits
    and heart rate zone breakdown. Use an activity_id from get_recent_activities."""
    from .tools.activities import get_activity_detail as _get

    result = _get(_get_client().api, activity_id=activity_id)
    return _to_json(result)


@mcp.tool()
def get_activities_in_range(
    start_date: str,
    end_date: str,
    activity_type: str | None = None,
) -> str:
    """Get Garmin activities between start_date and end_date (YYYY-MM-DD).
    Optionally filter by activity type."""
    from .tools.activities import get_activities_in_range as _get

    result = _get(
        _get_client().api,
        start_date=start_date,
        end_date=end_date,
        activity_type=activity_type,
    )
    return _to_json(result)


# --- Health tools ---


@mcp.tool()
def get_hrv_trend(days: int = 28) -> str:
    """Get Heart Rate Variability trend over recent days with 7-day rolling
    average. Useful for tracking recovery and training readiness."""
    from .tools.health import get_hrv_trend as _get

    result = _get(_get_client().api, days=days)
    return _to_json(result)


@mcp.tool()
def get_sleep_history(days: int = 14) -> str:
    """Get sleep data over recent days including sleep score, total duration,
    and time in each sleep stage (deep, light, REM, awake)."""
    from .tools.health import get_sleep_history as _get

    result = _get(_get_client().api, days=days)
    return _to_json(result)


@mcp.tool()
def get_body_battery(days: int = 7) -> str:
    """Get Garmin Body Battery levels over recent days including daily
    highest, lowest, charged, and drained values."""
    from .tools.health import get_body_battery as _get

    result = _get(_get_client().api, days=days)
    return _to_json(result)


@mcp.tool()
def get_resting_hr_trend(days: int = 14) -> str:
    """Get resting heart rate trend over recent days. Useful for tracking
    cardiovascular fitness and recovery."""
    from .tools.health import get_resting_hr_trend as _get

    result = _get(_get_client().api, days=days)
    return _to_json(result)


# --- Training tools ---


@mcp.tool()
def get_training_status() -> str:
    """Get current Garmin training status including VO2 max, training load,
    readiness score, and recovery time."""
    from .tools.training import get_training_status as _get

    result = _get(_get_client().api)
    return _to_json(result)


@mcp.tool()
def get_race_predictions() -> str:
    """Get predicted race finish times for common distances (5K, 10K,
    half marathon, marathon) based on your Garmin fitness data."""
    from .tools.training import get_race_predictions as _get

    result = _get(_get_client().api)
    return _to_json(result)


@mcp.tool()
def get_weekly_summary(target_date: str | None = None) -> str:
    """Get a composite weekly summary: total activities, distance, duration,
    average resting HR, average sleep score. Defaults to current week.
    Provide target_date (YYYY-MM-DD) for a specific week."""
    from .tools.training import get_weekly_summary as _get

    result = _get(_get_client().api, target_date=target_date)
    return _to_json(result)


def main():
    """Start the MCP server."""
    mode = os.environ.get("MCP_MODE", "stdio")
    if mode == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
