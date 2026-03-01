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
        results.append(
            {
                "workout_id": workout.get("workoutId"),
                "workout_name": workout.get("workoutName"),
                "sport_type": workout.get("sportType", {}).get("sportTypeKey")
                if isinstance(workout.get("sportType"), dict)
                else workout.get("sportType"),
                "created_date": workout.get("createdDate"),
                "updated_date": workout.get("updatedDate"),
                "estimated_duration_seconds": workout.get("estimatedDurationInSecs"),
                "estimated_distance_meters": workout.get("estimatedDistanceInMeters"),
            }
        )

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


def upload_running_workout(
    api: Garmin,
    workout_name: str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Upload a running workout to Garmin Connect.

    Args:
        api: Garmin API instance
        workout_name: Name for the workout
        steps: List of step dicts, each with:
            - type: "warmup" | "cooldown" | "interval" | "recovery" | "repeat"
            - duration_seconds: float (for warmup/cooldown/interval/recovery)
            - iterations: int (for repeat only)
            - steps: list of nested step dicts (for repeat only)
    """
    from garminconnect.workout import (
        RunningWorkout,
        WorkoutSegment,
        create_cooldown_step,
        create_interval_step,
        create_recovery_step,
        create_repeat_group,
        create_warmup_step,
    )

    def _build_step(step_def: dict[str, Any], order: int) -> Any:
        step_type = step_def.get("type", "interval")
        duration = float(step_def.get("duration_seconds", 300))

        if step_type == "warmup":
            return create_warmup_step(duration, step_order=order)
        elif step_type == "cooldown":
            return create_cooldown_step(duration, step_order=order)
        elif step_type == "recovery":
            return create_recovery_step(duration, step_order=order)
        elif step_type == "repeat":
            iterations = int(step_def.get("iterations", 1))
            nested = step_def.get("steps", [])
            nested_steps = [_build_step(s, i + 1) for i, s in enumerate(nested)]
            return create_repeat_group(iterations, nested_steps, step_order=order)
        else:  # interval
            return create_interval_step(duration, step_order=order)

    workout_steps = [_build_step(s, i + 1) for i, s in enumerate(steps)]

    # Estimate total duration from steps
    def _estimate_duration(step_list: list[dict[str, Any]]) -> float:
        total = 0.0
        for s in step_list:
            if s.get("type") == "repeat":
                iters = int(s.get("iterations", 1))
                total += iters * _estimate_duration(s.get("steps", []))
            else:
                total += float(s.get("duration_seconds", 300))
        return total

    estimated_duration = int(_estimate_duration(steps))

    workout = RunningWorkout(
        workoutName=workout_name,
        estimatedDurationInSecs=estimated_duration,
        workoutSegments=[
            WorkoutSegment(
                segmentOrder=1,
                sportType={"sportTypeId": 1, "sportTypeKey": "running"},
                workoutSteps=workout_steps,
            )
        ],
    )

    result = api.upload_running_workout(workout)
    return result if result else {}
