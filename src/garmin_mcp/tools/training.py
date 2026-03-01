"""MCP tools for Garmin Connect training status and predictions."""

from datetime import date, timedelta
from typing import Any

from garminconnect import Garmin

from .activities import get_activities_in_range
from .health import get_body_battery, get_resting_hr_trend, get_sleep_history


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


def get_recovery_snapshot(
    api: Garmin,
) -> dict[str, Any]:
    """Get a single-call recovery snapshot with all key metrics."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    result: dict[str, Any] = {"date": today}

    # HRV (last night)
    try:
        hrv_data = api.get_hrv_data(today)
        if hrv_data and hrv_data.get("hrvSummary"):
            s = hrv_data["hrvSummary"]
            result["hrv_last_night"] = s.get("lastNight")
            result["hrv_last_night_avg"] = s.get("lastNightAvg")
            result["hrv_status"] = s.get("status")
            result["hrv_baseline_low"] = s.get("baselineLowUpper")
            result["hrv_baseline_high"] = s.get("baselineBalancedUpper")
        else:
            result["hrv_last_night"] = None
    except Exception:
        result["hrv_last_night"] = None

    # Sleep (last night)
    try:
        sleep = api.get_sleep_data(today)
        if sleep:
            daily = sleep.get("dailySleepDTO", {})
            scores = daily.get("sleepScores", {})
            result["sleep_score"] = scores.get("overall", {}).get("value")
            result["sleep_duration_hours"] = (
                round(daily.get("sleepTimeSeconds", 0) / 3600, 1)
                if daily.get("sleepTimeSeconds")
                else None
            )
        else:
            result["sleep_score"] = None
    except Exception:
        result["sleep_score"] = None

    # Body battery (current)
    try:
        bb = get_body_battery(api, days=1)
        if bb:
            result["body_battery_current"] = bb[0].get("most_recent")
            result["body_battery_highest"] = bb[0].get("highest")
            result["body_battery_lowest"] = bb[0].get("lowest")
        else:
            result["body_battery_current"] = None
    except Exception:
        result["body_battery_current"] = None

    # Resting HR (yesterday, since today's may not be finalized)
    try:
        rhr = get_resting_hr_trend(api, days=2)
        for entry in rhr:
            if entry.get("date") == yesterday and entry.get("resting_hr"):
                result["resting_hr_yesterday"] = entry["resting_hr"]
                break
        else:
            result["resting_hr_yesterday"] = None
    except Exception:
        result["resting_hr_yesterday"] = None

    # Training readiness
    try:
        readiness = api.get_training_readiness(today)
        if readiness and isinstance(readiness, list) and len(readiness) > 0:
            r = readiness[0]
            result["readiness_score"] = r.get("score")
            result["readiness_level"] = r.get("level")
            result["recovery_time_hours"] = r.get("recoveryTimeInHours")
        elif readiness and isinstance(readiness, dict):
            result["readiness_score"] = readiness.get("score")
            result["readiness_level"] = readiness.get("level")
        else:
            result["readiness_score"] = None
    except Exception:
        result["readiness_score"] = None

    return result


def get_morning_readiness(
    api: Garmin,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Get morning training readiness over recent days."""
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(days)]
    results: list[dict[str, Any]] = []

    for d in reversed(dates):
        try:
            data = api.get_morning_training_readiness(d)
            if data:
                results.append({
                    "date": d,
                    "score": data.get("score"),
                    "level": data.get("level"),
                    "sleep_score_factor": data.get("sleepScorePercentage"),
                    "recovery_time_hours": data.get("recoveryTimeInHours"),
                    "hrv_status": data.get("hrvStatus"),
                    "acclimation_status": data.get("heatAcclimationStatus"),
                    "altitude_acclimation": data.get("altitudeAcclimationStatus"),
                })
            else:
                results.append({"date": d, "score": None})
        except Exception:
            results.append({"date": d, "score": None})

    return results


def get_max_metrics(
    api: Garmin,
) -> dict[str, Any]:
    """Get current max metrics (VO2 max, etc.)."""
    today = date.today().isoformat()
    try:
        data = api.get_max_metrics(today)
    except Exception:
        return {}

    if not data:
        return {}

    # API may return a list or dict
    entry = data[0] if isinstance(data, list) and data else data
    if not isinstance(entry, dict):
        return {}

    generic = entry.get("generic", {}) or {}
    cycling = entry.get("cycling", {}) or {}
    result: dict[str, Any] = {}

    if generic:
        result["vo2_max_running"] = generic.get("vo2MaxPreciseValue")
        result["fitness_age"] = generic.get("fitnessAge")
    if cycling:
        result["vo2_max_cycling"] = cycling.get("vo2MaxPreciseValue")

    result["updated"] = entry.get("calendarDate")
    return result


def get_endurance_score(
    api: Garmin,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Get endurance score for a single day or date range."""
    if start_date is None:
        start_date = date.today().isoformat()

    try:
        if end_date:
            data = api.get_endurance_score(start_date, end_date)
        else:
            data = api.get_endurance_score(start_date)
    except Exception:
        return {}

    if not data:
        return {}

    # Single-day response
    if isinstance(data, dict) and "overallScore" in data:
        return {
            "date": start_date,
            "overall_score": data.get("overallScore"),
            "running_score": data.get("runningScore"),
            "cycling_score": data.get("cyclingScore"),
            "swimming_score": data.get("swimmingScore"),
        }

    return data


def get_lactate_threshold(
    api: Garmin,
) -> dict[str, Any]:
    """Get latest lactate threshold data (heart rate, speed, power)."""
    try:
        data = api.get_lactate_threshold(latest=True)
    except Exception:
        return {}

    if not data:
        return {}

    result: dict[str, Any] = {}

    shr = data.get("speed_and_heart_rate", {})
    if shr:
        result["heart_rate_bpm"] = shr.get("heartRate")
        speed_mps = shr.get("speed")
        if speed_mps:
            result["speed_m_per_s"] = round(speed_mps, 3)
            # Convert m/s to min/km pace
            pace_secs = 1000.0 / speed_mps
            result["pace_min_per_km"] = _format_time(pace_secs)
        result["date"] = shr.get("calendarDate")

    power = data.get("power", {})
    if power:
        result["ftp_watts"] = power.get("functionalThresholdPower")

    return result


def get_progress_summary(
    api: Garmin,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Get progress summary between two dates."""
    try:
        data = api.get_progress_summary_between_dates(start_date, end_date)
    except Exception:
        return {}

    if not data:
        return {}

    return data


def get_personal_records(
    api: Garmin,
) -> list[dict[str, Any]]:
    """Get personal records across all activity types."""
    try:
        data = api.get_personal_record()
    except Exception:
        return []

    if not data:
        return []

    if not isinstance(data, list):
        data = [data]

    results: list[dict[str, Any]] = []
    for record in data:
        if not isinstance(record, dict):
            continue
        results.append({
            "activity_type": record.get("typeKey"),
            "record_type": record.get("personalRecordType"),
            "value": record.get("value"),
            "activity_id": record.get("activityId"),
            "activity_name": record.get("activityName"),
            "date": record.get("prStartTimeGMT") or record.get("calendarDate"),
        })

    return results
