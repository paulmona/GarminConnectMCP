"""Tests for garmin_mcp.tools.workouts."""

from unittest.mock import MagicMock

from garmin_mcp.tools.workouts import (
    get_training_plans,
    get_workout_by_id,
    get_workouts,
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
