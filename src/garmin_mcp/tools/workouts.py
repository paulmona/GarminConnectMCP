"""MCP tools for Garmin Connect workouts and training plans."""

from typing import Any

from garminconnect import Garmin


def get_workouts(
    api: Garmin,
    start: int = 0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get saved workouts from Garmin Connect."""
    try:
        data = api.get_workouts(start, limit)
    except Exception:
        return []

    if not data:
        return []

    if not isinstance(data, list):
        data = [data]

    results: list[dict[str, Any]] = []
    for workout in data:
        if not isinstance(workout, dict):
            continue
        results.append({
            "workout_id": workout.get("workoutId"),
            "workout_name": workout.get("workoutName"),
            "sport_type": workout.get("sportType", {}).get("sportTypeKey")
            if isinstance(workout.get("sportType"), dict)
            else workout.get("sportType"),
            "created_date": workout.get("createdDate"),
            "updated_date": workout.get("updatedDate"),
            "estimated_duration_seconds": workout.get("estimatedDurationInSecs"),
            "estimated_distance_meters": workout.get("estimatedDistanceInMeters"),
        })

    return results


def get_workout_by_id(
    api: Garmin,
    workout_id: str,
) -> dict[str, Any]:
    """Get details of a specific saved workout."""
    try:
        data = api.get_workout_by_id(workout_id)
    except Exception:
        return {}

    if not data:
        return {}

    return data


def get_training_plans(
    api: Garmin,
) -> list[dict[str, Any]]:
    """Get training plans from Garmin Connect."""
    try:
        data = api.get_training_plans()
    except Exception:
        return []

    if not data:
        return []

    if not isinstance(data, list):
        data = [data]

    return data
