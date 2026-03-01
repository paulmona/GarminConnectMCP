"""Tests for garmin_mcp.tools.workouts."""

from unittest.mock import MagicMock

from garmin_mcp.tools.workouts import (
    get_training_plans,
    get_workout_by_id,
    get_workouts,
    upload_running_workout,
)


# --- get_workouts ---

class TestGetWorkouts:

    def test_returns_workouts(self):
        api = MagicMock()
        api.get_workouts.return_value = [
            {
                "workoutId": 12345,
                "workoutName": "Easy Run",
                "sportType": {"sportTypeKey": "running"},
                "createdDate": "2025-01-10T10:00:00",
                "updatedDate": "2025-01-10T10:00:00",
                "estimatedDurationInSecs": 1800,
                "estimatedDistanceInMeters": 5000,
            },
            {
                "workoutId": 67890,
                "workoutName": "Tempo Run",
                "sportType": {"sportTypeKey": "running"},
                "createdDate": "2025-01-12T10:00:00",
                "updatedDate": "2025-01-12T10:00:00",
                "estimatedDurationInSecs": 3600,
                "estimatedDistanceInMeters": 10000,
            },
        ]

        result = get_workouts(api, start=0, limit=10)

        assert len(result) == 2
        assert result[0]["workout_id"] == 12345
        assert result[0]["workout_name"] == "Easy Run"
        assert result[0]["sport_type"] == "running"
        assert result[0]["estimated_duration_seconds"] == 1800

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_workouts.return_value = None

        assert get_workouts(api) == []

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_workouts.side_effect = Exception("fail")

        assert get_workouts(api) == []


# --- get_workout_by_id ---

class TestGetWorkoutById:

    def test_returns_workout_detail(self):
        api = MagicMock()
        api.get_workout_by_id.return_value = {
            "workoutId": 12345,
            "workoutName": "Easy Run",
            "steps": [{"stepType": "warmup"}, {"stepType": "interval"}],
        }

        result = get_workout_by_id(api, workout_id="12345")

        assert result["workoutId"] == 12345
        assert result["workoutName"] == "Easy Run"
        assert len(result["steps"]) == 2

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_workout_by_id.return_value = None

        assert get_workout_by_id(api, workout_id="12345") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_workout_by_id.side_effect = Exception("fail")

        assert get_workout_by_id(api, workout_id="12345") == {}


# --- get_training_plans ---

class TestGetTrainingPlans:

    def test_returns_training_plans(self):
        api = MagicMock()
        api.get_training_plans.return_value = [
            {"planName": "5K Beginner", "status": "ACTIVE"},
            {"planName": "10K Intermediate", "status": "COMPLETED"},
        ]

        result = get_training_plans(api)

        assert len(result) == 2
        assert result[0]["planName"] == "5K Beginner"

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_training_plans.return_value = None

        assert get_training_plans(api) == []

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_training_plans.side_effect = Exception("fail")

        assert get_training_plans(api) == []

    def test_handles_single_dict_response(self):
        api = MagicMock()
        api.get_training_plans.return_value = {"planName": "Marathon Plan"}

        result = get_training_plans(api)

        assert len(result) == 1
        assert result[0]["planName"] == "Marathon Plan"


# --- upload_running_workout ---

class TestUploadRunningWorkout:

    def test_uploads_simple_workout(self):
        api = MagicMock()
        api.upload_running_workout.return_value = {
            "workoutId": 99999,
            "workoutName": "Easy Run",
        }

        steps = [
            {"type": "warmup", "duration_seconds": 300},
            {"type": "interval", "duration_seconds": 1200},
            {"type": "cooldown", "duration_seconds": 300},
        ]

        result = upload_running_workout(api, workout_name="Easy Run", steps=steps)

        assert result["workoutId"] == 99999
        api.upload_running_workout.assert_called_once()
        workout_arg = api.upload_running_workout.call_args[0][0]
        assert workout_arg.workoutName == "Easy Run"
        assert workout_arg.estimatedDurationInSecs == 1800

    def test_uploads_interval_workout_with_repeats(self):
        api = MagicMock()
        api.upload_running_workout.return_value = {"workoutId": 88888}

        steps = [
            {"type": "warmup", "duration_seconds": 600},
            {
                "type": "repeat",
                "iterations": 5,
                "steps": [
                    {"type": "interval", "duration_seconds": 60},
                    {"type": "recovery", "duration_seconds": 90},
                ],
            },
            {"type": "cooldown", "duration_seconds": 300},
        ]

        result = upload_running_workout(api, workout_name="5x1min", steps=steps)

        assert result["workoutId"] == 88888
        workout_arg = api.upload_running_workout.call_args[0][0]
        # 600 + 5*(60+90) + 300 = 1650
        assert workout_arg.estimatedDurationInSecs == 1650

    def test_returns_empty_on_none_response(self):
        api = MagicMock()
        api.upload_running_workout.return_value = None

        steps = [{"type": "interval", "duration_seconds": 600}]
        result = upload_running_workout(api, workout_name="Test", steps=steps)

        assert result == {}

    def test_raises_on_api_exception(self):
        import pytest

        api = MagicMock()
        api.upload_running_workout.side_effect = Exception("upload failed")

        with pytest.raises(Exception, match="upload failed"):
            upload_running_workout(
                api, workout_name="Test",
                steps=[{"type": "interval", "duration_seconds": 300}],
            )
