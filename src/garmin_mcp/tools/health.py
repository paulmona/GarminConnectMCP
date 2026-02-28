"""MCP tools for Garmin Connect health metrics."""

from datetime import date, timedelta
from typing import Any

from garminconnect import Garmin


def _date_range(days: int) -> list[str]:
    """Return list of date strings (YYYY-MM-DD) for the last N days."""
    today = date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(days)]


def get_hrv_trend(
    api: Garmin,
    days: int = 28,
) -> dict[str, Any]:
    """Get HRV trend over recent days with 7-day rolling average."""
    dates = _date_range(days)
    daily_values: list[dict[str, Any]] = []

    for d in reversed(dates):
        try:
            data = api.get_hrv_data(d)
            if data and data.get("hrvSummary"):
                summary = data["hrvSummary"]
                daily_values.append({
                    "date": d,
                    "weekly_avg": summary.get("weeklyAvg"),
                    "last_night": summary.get("lastNight"),
                    "last_night_avg": summary.get("lastNightAvg"),
                    "last_night_5_min_high": summary.get("lastNight5MinHigh"),
                    "baseline_low": summary.get("baselineLowUpper"),
                    "baseline_balanced_low": summary.get(
                        "baselineBalancedLow"
                    ),
                    "baseline_balanced_upper": summary.get(
                        "baselineBalancedUpper"
                    ),
                    "status": summary.get("status"),
                })
            else:
                daily_values.append({"date": d, "weekly_avg": None})
        except Exception:
            daily_values.append({"date": d, "weekly_avg": None})

    # Compute 7-day rolling average
    valid_vals = [
        v["last_night_avg"]
        for v in daily_values
        if v.get("last_night_avg") is not None
    ]
    rolling_avg_7d = (
        round(sum(valid_vals[-7:]) / len(valid_vals[-7:]), 1)
        if len(valid_vals) >= 7
        else None
    )

    return {
        "days_requested": days,
        "rolling_avg_7d": rolling_avg_7d,
        "daily": daily_values,
    }


def get_sleep_history(
    api: Garmin,
    days: int = 14,
) -> list[dict[str, Any]]:
    """Get sleep data over recent days."""
    dates = _date_range(days)
    results: list[dict[str, Any]] = []

    for d in reversed(dates):
        try:
            data = api.get_sleep_data(d)
            if not data:
                results.append({"date": d, "sleep_score": None})
                continue

            daily_sleep = data.get("dailySleepDTO", {})
            results.append({
                "date": d,
                "sleep_score": daily_sleep.get(
                    "sleepScores", {}
                ).get("overall", {}).get("value"),
                "total_sleep_seconds": daily_sleep.get(
                    "sleepTimeSeconds"
                ),
                "deep_sleep_seconds": daily_sleep.get(
                    "deepSleepSeconds"
                ),
                "light_sleep_seconds": daily_sleep.get(
                    "lightSleepSeconds"
                ),
                "rem_sleep_seconds": daily_sleep.get("remSleepSeconds"),
                "awake_seconds": daily_sleep.get("awakeSleepSeconds"),
            })
        except Exception:
            results.append({"date": d, "sleep_score": None})

    return results


def get_body_battery(
    api: Garmin,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Get body battery daily summary over recent days."""
    today = date.today()
    start = (today - timedelta(days=days - 1)).isoformat()
    end = today.isoformat()

    try:
        data = api.get_body_battery(start, end)
    except Exception:
        return []

    if not data:
        return []

    results: list[dict[str, Any]] = []
    for day_data in data:
        results.append({
            "date": day_data.get("calendarDate"),
            "charged": day_data.get("charged"),
            "drained": day_data.get("drained"),
            "start_level": day_data.get("startTimestampGMT"),
            "end_level": day_data.get("endTimestampGMT"),
            "highest": day_data.get("bodyBatteryHighestValue"),
            "lowest": day_data.get("bodyBatteryLowestValue"),
            "most_recent": day_data.get(
                "bodyBatteryMostRecentValue"
            ),
        })
    return results


def get_resting_hr_trend(
    api: Garmin,
    days: int = 14,
) -> list[dict[str, Any]]:
    """Get resting heart rate trend over recent days."""
    dates = _date_range(days)
    results: list[dict[str, Any]] = []

    for d in reversed(dates):
        try:
            data = api.get_rhr_day(d)
            rhr = None
            if data and isinstance(data, dict):
                rhr_list = (
                    data.get("allMetrics", {})
                    .get("metricsMap", {})
                    .get("WELLNESS_RESTING_HEART_RATE", [])
                )
                if rhr_list:
                    raw = rhr_list[0].get("value")
                    rhr = int(raw) if raw is not None else None
            results.append({"date": d, "resting_hr": rhr})
        except Exception:
            results.append({"date": d, "resting_hr": None})

    return results
