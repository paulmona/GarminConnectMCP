"""MCP tools for Garmin Connect training status and predictions."""

from datetime import date, timedelta
from typing import Any

from garminconnect import Garmin

from .activities import get_activities_in_range
from .health import get_resting_hr_trend, get_sleep_history


def get_training_status(
    api: Garmin,
) -> dict[str, Any]:
    """Get current training status and readiness."""
    today = date.today().isoformat()
    result: dict[str, Any] = {}

    try:
        status = api.get_training_status(today)
        if status:
            result["training_status"] = status.get(
                "trainingStatusLabel"
            )
            result["vo2_max"] = status.get("vo2Max")
            result["load_7_day"] = status.get("weeklyTrainingLoad")
            result["load_focus"] = status.get("trainingLoadFocus")
            result["acute_load"] = status.get("acuteTrainingLoad")
            result["chronic_load"] = status.get(
                "currentDayTrainingLoad"
            )
    except Exception:
        result["training_status"] = None

    try:
        readiness = api.get_training_readiness(today)
        if readiness and isinstance(readiness, list) and len(readiness) > 0:
            r = readiness[0]
            result["readiness_score"] = r.get("score")
            result["readiness_level"] = r.get("level")
            result["sleep_score_factor"] = r.get(
                "sleepScorePercentage"
            )
            result["recovery_time_hours"] = r.get(
                "recoveryTimeInHours"
            )
            result["hrv_status"] = r.get("hrvStatus")
        elif readiness and isinstance(readiness, dict):
            result["readiness_score"] = readiness.get("score")
            result["readiness_level"] = readiness.get("level")
    except Exception:
        result["readiness_score"] = None

    return result


def _format_time(seconds: float | None) -> str | None:
    """Convert seconds to H:MM:SS format."""
    if seconds is None or seconds <= 0:
        return None
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}"


def get_race_predictions(
    api: Garmin,
) -> dict[str, Any]:
    """Get predicted race finish times."""
    try:
        data = api.get_race_predictions()
    except Exception:
        return {}

    if not data:
        return {}

    predictions: dict[str, Any] = {}
    for entry in data if isinstance(data, list) else [data]:
        race = entry.get("racePredictionType", "")
        time_secs = entry.get("predictedTime")
        if race and time_secs:
            predictions[race] = {
                "predicted_seconds": time_secs,
                "predicted_time": _format_time(time_secs),
            }

    return predictions


def get_weekly_summary(
    api: Garmin,
    target_date: str | None = None,
) -> dict[str, Any]:
    """Get a composite weekly summary: activities, avg RHR, avg HRV, avg sleep."""
    if target_date:
        ref = date.fromisoformat(target_date)
    else:
        ref = date.today()

    # Week boundaries (Monday-Sunday)
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    start = monday.isoformat()
    end = sunday.isoformat()

    result: dict[str, Any] = {"week_start": start, "week_end": end}

    # Activities
    activities = get_activities_in_range(api, start, end)
    result["total_activities"] = len(activities)
    result["total_distance_km"] = round(
        sum(a.get("distance_km") or 0 for a in activities), 2
    )
    result["total_duration_seconds"] = round(
        sum(a.get("duration_seconds") or 0 for a in activities), 0
    )
    result["activities"] = activities

    # Avg resting HR for the week
    rhr_data = get_resting_hr_trend(api, days=7)
    rhr_vals = [
        d["resting_hr"] for d in rhr_data if d.get("resting_hr") is not None
    ]
    result["avg_resting_hr"] = (
        round(sum(rhr_vals) / len(rhr_vals), 1) if rhr_vals else None
    )

    # Avg sleep score for the week
    sleep_data = get_sleep_history(api, days=7)
    sleep_scores = [
        d["sleep_score"]
        for d in sleep_data
        if d.get("sleep_score") is not None
    ]
    result["avg_sleep_score"] = (
        round(sum(sleep_scores) / len(sleep_scores), 1)
        if sleep_scores
        else None
    )

    return result
