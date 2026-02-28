"""MCP tools for Garmin Connect weight and body composition data."""

from datetime import date, timedelta
from typing import Any

from garminconnect import Garmin


def get_weight_trend(
    api: Garmin,
    days: int = 30,
) -> dict[str, Any]:
    """Get weight trend over recent days."""
    today = date.today()
    start = (today - timedelta(days=days - 1)).isoformat()
    end = today.isoformat()

    try:
        data = api.get_weigh_ins(start, end)
    except Exception:
        return {"days_requested": days, "entries": [], "summary": None}

    entries = []
    if data and isinstance(data, dict):
        daily_weigh_ins = data.get("dailyWeighIns", [])
        for entry in daily_weigh_ins:
            weight_kg = entry.get("weight")
            if weight_kg is not None:
                weight_kg = round(weight_kg / 1000, 2)  # grams → kg
            entries.append({
                "date": entry.get("calendarDate"),
                "weight_kg": weight_kg,
                "weight_lbs": round(weight_kg * 2.20462, 1) if weight_kg else None,
                "bmi": entry.get("bmi"),
            })

    # Summary stats
    weights = [e["weight_kg"] for e in entries if e["weight_kg"] is not None]
    summary = None
    if weights:
        summary = {
            "latest_kg": weights[-1],
            "latest_lbs": round(weights[-1] * 2.20462, 1),
            "min_kg": min(weights),
            "max_kg": max(weights),
            "avg_kg": round(sum(weights) / len(weights), 2),
            "change_kg": round(weights[-1] - weights[0], 2) if len(weights) > 1 else None,
        }

    return {
        "days_requested": days,
        "entries": entries,
        "summary": summary,
    }


def get_body_composition(
    api: Garmin,
    days: int = 30,
) -> dict[str, Any]:
    """Get body composition trend over recent days."""
    today = date.today()
    start = (today - timedelta(days=days - 1)).isoformat()
    end = today.isoformat()

    try:
        data = api.get_body_composition(start, end)
    except Exception:
        return {"days_requested": days, "entries": []}

    entries = []
    if data and isinstance(data, dict):
        total_average = data.get("totalAverage", {})
        composition_list = data.get("dateWeightList", [])

        for entry in composition_list:
            weight_kg = entry.get("weight")
            if weight_kg is not None:
                weight_kg = round(weight_kg / 1000, 2)  # grams → kg
            entries.append({
                "date": entry.get("calendarDate"),
                "weight_kg": weight_kg,
                "bmi": entry.get("bmi"),
                "body_fat_pct": entry.get("bodyFat"),
                "body_water_pct": entry.get("bodyWater"),
                "bone_mass_kg": round(entry["boneMass"] / 1000, 2)
                    if entry.get("boneMass") else None,
                "muscle_mass_kg": round(entry["muscleMass"] / 1000, 2)
                    if entry.get("muscleMass") else None,
                "visceral_fat": entry.get("visceralFat"),
                "metabolic_age": entry.get("metabolicAge"),
            })

        return {
            "days_requested": days,
            "period_average": {
                "weight_kg": round(total_average["weight"] / 1000, 2)
                    if total_average.get("weight") else None,
                "bmi": total_average.get("bmi"),
                "body_fat_pct": total_average.get("bodyFat"),
                "muscle_mass_kg": round(total_average["muscleMass"] / 1000, 2)
                    if total_average.get("muscleMass") else None,
            } if total_average else None,
            "entries": entries,
        }

    return {"days_requested": days, "entries": []}
