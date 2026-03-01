"""MCP tools for Garmin Connect activities."""

from typing import Any

from garminconnect import Garmin


def _format_pace(speed_mps: float | None) -> str | None:
    """Convert m/s to min:sec/km pace string."""
    if not speed_mps or speed_mps <= 0:
        return None
    pace_sec = 1000.0 / speed_mps
    minutes = int(pace_sec // 60)
    seconds = int(pace_sec % 60)
    return f"{minutes}:{seconds:02d}/km"


def _summarize_activity(act: dict[str, Any]) -> dict[str, Any]:
    """Extract useful fields from a raw Garmin activity dict."""
    distance_m = act.get("distance")
    return {
        "activity_id": act.get("activityId"),
        "name": act.get("activityName"),
        "type": act.get("activityType", {}).get("typeKey"),
        "date": act.get("startTimeLocal"),
        "distance_km": round(distance_m / 1000, 2) if distance_m else None,
        "duration_seconds": act.get("duration"),
        "avg_hr": act.get("averageHR"),
        "max_hr": act.get("maxHR"),
        "avg_pace": _format_pace(act.get("averageSpeed")),
        "calories": act.get("calories"),
        "elevation_gain": act.get("elevationGain"),
    }


def get_recent_activities(
    api: Garmin,
    limit: int = 10,
    activity_type: str | None = None,
) -> list[dict[str, Any]]:
    """Get recent activities, optionally filtered by type."""
    activities = api.get_activities(0, limit, activitytype=activity_type)
    if not activities:
        return []
    return [_summarize_activity(a) for a in activities]


def get_activity_detail(
    api: Garmin,
    activity_id: str,
) -> dict[str, Any]:
    """Get full detail for a single activity including splits and HR zones."""
    summary = api.get_activity(activity_id)
    base = _summarize_activity(summary)

    # Splits
    try:
        splits_data = api.get_activity_splits(activity_id)
        laps = []
        for split in (splits_data or {}).get("lapDTOs", []):
            distance_m = split.get("distance")
            laps.append(
                {
                    "lap_number": split.get("lapIndex"),
                    "distance_km": (round(distance_m / 1000, 2) if distance_m else None),
                    "duration_seconds": split.get("duration"),
                    "avg_hr": split.get("averageHR"),
                    "max_hr": split.get("maxHR"),
                    "avg_pace": _format_pace(split.get("averageSpeed")),
                    "calories": split.get("calories"),
                }
            )
        base["laps"] = laps
    except Exception:
        base["laps"] = []

    # HR zones
    try:
        hr_zones_data = api.get_activity_hr_in_timezones(activity_id)
        zones = []
        for zone_list in hr_zones_data or []:
            for z in zone_list.get("zones", []):
                zones.append(
                    {
                        "zone": z.get("zoneNumber"),
                        "zone_low_hr": z.get("zoneLowBoundary"),
                        "zone_high_hr": z.get("zoneHighBoundary"),
                        "seconds_in_zone": z.get("secsInZone"),
                    }
                )
            if zones:
                break  # Only take the first set
        base["hr_zones"] = zones
    except Exception:
        base["hr_zones"] = []

    return base


def get_activities_in_range(
    api: Garmin,
    start_date: str,
    end_date: str,
    activity_type: str | None = None,
) -> list[dict[str, Any]]:
    """Get activities between start_date and end_date (YYYY-MM-DD)."""
    activities = api.get_activities_by_date(start_date, end_date, activitytype=activity_type)
    if not activities:
        return []
    return [_summarize_activity(a) for a in activities]


def get_activity_typed_splits(
    api: Garmin,
    activity_id: str,
) -> dict[str, Any]:
    """Get typed splits (e.g., run/walk segments) for an activity."""
    try:
        data = api.get_activity_typed_splits(activity_id)
    except Exception:
        return {}

    if not data:
        return {}

    return data


def get_activity_split_summaries(
    api: Garmin,
    activity_id: str,
) -> dict[str, Any]:
    """Get split summary data for an activity."""
    try:
        data = api.get_activity_split_summaries(activity_id)
    except Exception:
        return {}

    if not data:
        return {}

    return data


def get_activity_weather(
    api: Garmin,
    activity_id: str,
) -> dict[str, Any]:
    """Get weather conditions during an activity."""
    try:
        data = api.get_activity_weather(activity_id)
    except Exception:
        return {}

    if not data:
        return {}

    return data


def get_activity_power_zones(
    api: Garmin,
    activity_id: str,
) -> dict[str, Any]:
    """Get power zone distribution for an activity."""
    try:
        data = api.get_activity_power_in_timezones(activity_id)
    except Exception:
        return {}

    if not data:
        return {}

    return data
