"""Tests for garmin_mcp.tools.training."""

from datetime import date
from unittest.mock import MagicMock, patch

from garmin_mcp.tools.training import (
    _format_time,
    get_endurance_score,
    get_lactate_threshold,
    get_max_metrics,
    get_morning_readiness,
    get_personal_records,
    get_progress_summary,
    get_race_predictions,
    get_recovery_snapshot,
    get_training_status,
    get_weekly_summary,
)


# --- _format_time ---

class TestFormatTime:

    def test_hours_minutes_seconds(self):
        assert _format_time(3661.0) == "1:01:01"

    def test_exact_hour(self):
        assert _format_time(3600.0) == "1:00:00"

    def test_under_one_hour(self):
        assert _format_time(1500.0) == "0:25:00"

    def test_returns_none_for_none(self):
        assert _format_time(None) is None

    def test_returns_none_for_zero(self):
        assert _format_time(0.0) is None

    def test_returns_none_for_negative(self):
        assert _format_time(-10.0) is None


# --- get_training_status ---

class TestGetTrainingStatus:

    @patch("garmin_mcp.tools.training.date")
    def test_returns_training_status(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_training_status.return_value = {
            "trainingStatusLabel": "PRODUCTIVE",
            "vo2Max": 52.0,
            "weeklyTrainingLoad": 350,
            "trainingLoadFocus": "HIGH_AEROBIC",
            "acuteTrainingLoad": 120,
            "currentDayTrainingLoad": 80,
        }
        api.get_training_readiness.return_value = [
            {
                "score": 72,
                "level": "MODERATE",
                "sleepScorePercentage": 85,
                "recoveryTimeInHours": 12,
                "hrvStatus": "BALANCED",
            }
        ]

        result = get_training_status(api)

        assert result["training_status"] == "PRODUCTIVE"
        assert result["vo2_max"] == 52.0
        assert result["readiness_score"] == 72
        assert result["readiness_level"] == "MODERATE"
        assert result["recovery_time_hours"] == 12

    @patch("garmin_mcp.tools.training.date")
    def test_handles_training_status_exception(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_training_status.side_effect = Exception("api error")
        api.get_training_readiness.return_value = []

        result = get_training_status(api)

        assert result["training_status"] is None

    @patch("garmin_mcp.tools.training.date")
    def test_handles_readiness_exception(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_training_status.return_value = {
            "trainingStatusLabel": "PRODUCTIVE",
        }
        api.get_training_readiness.side_effect = Exception("error")

        result = get_training_status(api)

        assert result["training_status"] == "PRODUCTIVE"
        assert result["readiness_score"] is None

    @patch("garmin_mcp.tools.training.date")
    def test_handles_readiness_as_dict(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_training_status.return_value = {}
        api.get_training_readiness.return_value = {
            "score": 80,
            "level": "HIGH",
        }

        result = get_training_status(api)

        assert result["readiness_score"] == 80
        assert result["readiness_level"] == "HIGH"


# --- get_race_predictions ---

class TestGetRacePredictions:

    def test_returns_predictions(self):
        api = MagicMock()
        api.get_race_predictions.return_value = [
            {"racePredictionType": "5K", "predictedTime": 1200.0},
            {"racePredictionType": "10K", "predictedTime": 2600.0},
        ]

        result = get_race_predictions(api)

        assert "5K" in result
        assert result["5K"]["predicted_seconds"] == 1200.0
        assert result["5K"]["predicted_time"] == "0:20:00"

    def test_handles_single_dict_response(self):
        api = MagicMock()
        api.get_race_predictions.return_value = {
            "racePredictionType": "HALF_MARATHON",
            "predictedTime": 5400.0,
        }

        result = get_race_predictions(api)

        assert "HALF_MARATHON" in result

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_race_predictions.side_effect = Exception("error")

        assert get_race_predictions(api) == {}

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_race_predictions.return_value = None

        assert get_race_predictions(api) == {}

    def test_skips_entries_without_time(self):
        api = MagicMock()
        api.get_race_predictions.return_value = [
            {"racePredictionType": "5K", "predictedTime": None},
        ]

        result = get_race_predictions(api)

        assert result == {}


# --- get_weekly_summary ---

class TestGetWeeklySummary:

    @patch("garmin_mcp.tools.training.get_sleep_history")
    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_activities_in_range")
    @patch("garmin_mcp.tools.training.date")
    def test_returns_composite_summary(
        self, mock_date, mock_activities, mock_rhr, mock_sleep,
    ):
        mock_date.today.return_value = date(2025, 1, 15)  # Wednesday
        mock_date.fromisoformat = date.fromisoformat
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_activities.return_value = [
            {"distance_km": 5.0, "duration_seconds": 1500},
            {"distance_km": 10.0, "duration_seconds": 3000},
        ]
        mock_rhr.return_value = [
            {"resting_hr": 58},
            {"resting_hr": 60},
        ]
        mock_sleep.return_value = [
            {"sleep_score": 80},
            {"sleep_score": 90},
        ]

        result = get_weekly_summary(api=MagicMock())

        assert result["week_start"] == "2025-01-13"  # Monday
        assert result["week_end"] == "2025-01-19"    # Sunday
        assert result["total_activities"] == 2
        assert result["total_distance_km"] == 15.0
        assert result["total_duration_seconds"] == 4500
        assert result["avg_resting_hr"] == 59.0
        assert result["avg_sleep_score"] == 85.0

    @patch("garmin_mcp.tools.training.get_sleep_history")
    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_activities_in_range")
    @patch("garmin_mcp.tools.training.date")
    def test_accepts_target_date(
        self, mock_date, mock_activities, mock_rhr, mock_sleep,
    ):
        mock_date.fromisoformat = date.fromisoformat
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_activities.return_value = []
        mock_rhr.return_value = []
        mock_sleep.return_value = []

        result = get_weekly_summary(api=MagicMock(), target_date="2025-01-06")

        # Jan 6, 2025 is a Monday
        assert result["week_start"] == "2025-01-06"
        assert result["week_end"] == "2025-01-12"

    @patch("garmin_mcp.tools.training.get_sleep_history")
    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_activities_in_range")
    @patch("garmin_mcp.tools.training.date")
    def test_handles_no_data(
        self, mock_date, mock_activities, mock_rhr, mock_sleep,
    ):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_activities.return_value = []
        mock_rhr.return_value = []
        mock_sleep.return_value = []

        result = get_weekly_summary(api=MagicMock())

        assert result["total_activities"] == 0
        assert result["total_distance_km"] == 0
        assert result["avg_resting_hr"] is None
        assert result["avg_sleep_score"] is None

    @patch("garmin_mcp.tools.training.get_sleep_history")
    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_activities_in_range")
    @patch("garmin_mcp.tools.training.date")
    def test_handles_none_distance_in_activities(
        self, mock_date, mock_activities, mock_rhr, mock_sleep,
    ):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_activities.return_value = [
            {"distance_km": None, "duration_seconds": 1500},
        ]
        mock_rhr.return_value = []
        mock_sleep.return_value = []

        result = get_weekly_summary(api=MagicMock())

        assert result["total_distance_km"] == 0


# --- get_recovery_snapshot ---

def _full_recovery_api():
    """Create a mock API that returns full recovery data."""
    api = MagicMock()
    api.get_hrv_data.return_value = {
        "hrvSummary": {
            "lastNight": 42,
            "lastNightAvg": 40,
            "status": "BALANCED",
            "baselineLowUpper": 30,
            "baselineBalancedUpper": 50,
        }
    }
    api.get_sleep_data.return_value = {
        "dailySleepDTO": {
            "sleepScores": {"overall": {"value": 85}},
            "sleepTimeSeconds": 28800,
        }
    }
    api.get_training_readiness.return_value = [
        {
            "score": 72,
            "level": "MODERATE",
            "recoveryTimeInHours": 12,
        }
    ]
    return api


class TestGetRecoverySnapshot:

    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_body_battery")
    @patch("garmin_mcp.tools.training.date")
    def test_returns_all_expected_keys(
        self, mock_date, mock_bb, mock_rhr,
    ):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_bb.return_value = [
            {"most_recent": 55, "highest": 90, "lowest": 20}
        ]
        mock_rhr.return_value = [
            {"date": "2025-01-14", "resting_hr": 58},
            {"date": "2025-01-15", "resting_hr": 60},
        ]

        api = _full_recovery_api()
        result = get_recovery_snapshot(api)

        expected_keys = {
            "date",
            "hrv_last_night",
            "hrv_last_night_avg",
            "hrv_status",
            "hrv_baseline_low",
            "hrv_baseline_high",
            "sleep_score",
            "sleep_duration_hours",
            "body_battery_current",
            "body_battery_highest",
            "body_battery_lowest",
            "resting_hr_yesterday",
            "readiness_score",
            "readiness_level",
            "recovery_time_hours",
        }
        assert expected_keys.issubset(result.keys())
        assert result["hrv_last_night"] == 42
        assert result["hrv_status"] == "BALANCED"
        assert result["sleep_score"] == 85
        assert result["sleep_duration_hours"] == 8.0
        assert result["body_battery_current"] == 55
        assert result["resting_hr_yesterday"] == 58
        assert result["readiness_score"] == 72

    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_body_battery")
    @patch("garmin_mcp.tools.training.date")
    def test_date_is_today_iso(self, mock_date, mock_bb, mock_rhr):
        mock_date.today.return_value = date(2025, 3, 22)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_bb.return_value = []
        mock_rhr.return_value = []

        api = MagicMock()
        api.get_hrv_data.return_value = None
        api.get_sleep_data.return_value = None
        api.get_training_readiness.return_value = None

        result = get_recovery_snapshot(api)

        assert result["date"] == "2025-03-22"

    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_body_battery")
    @patch("garmin_mcp.tools.training.date")
    def test_hrv_failure_returns_none(self, mock_date, mock_bb, mock_rhr):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_bb.return_value = [{"most_recent": 55, "highest": 90, "lowest": 20}]
        mock_rhr.return_value = [{"date": "2025-01-14", "resting_hr": 58}]

        api = _full_recovery_api()
        api.get_hrv_data.side_effect = Exception("HRV API down")

        result = get_recovery_snapshot(api)

        assert result["hrv_last_night"] is None
        # Other sections still populated
        assert result["sleep_score"] == 85
        assert result["readiness_score"] == 72

    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_body_battery")
    @patch("garmin_mcp.tools.training.date")
    def test_sleep_failure_returns_none(self, mock_date, mock_bb, mock_rhr):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_bb.return_value = [{"most_recent": 55, "highest": 90, "lowest": 20}]
        mock_rhr.return_value = [{"date": "2025-01-14", "resting_hr": 58}]

        api = _full_recovery_api()
        api.get_sleep_data.side_effect = Exception("Sleep API down")

        result = get_recovery_snapshot(api)

        assert result["sleep_score"] is None
        assert result["hrv_last_night"] == 42

    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_body_battery")
    @patch("garmin_mcp.tools.training.date")
    def test_body_battery_failure_returns_none(
        self, mock_date, mock_bb, mock_rhr,
    ):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_bb.side_effect = Exception("BB API down")
        mock_rhr.return_value = [{"date": "2025-01-14", "resting_hr": 58}]

        api = _full_recovery_api()
        result = get_recovery_snapshot(api)

        assert result["body_battery_current"] is None
        assert result["hrv_last_night"] == 42

    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_body_battery")
    @patch("garmin_mcp.tools.training.date")
    def test_rhr_failure_returns_none(self, mock_date, mock_bb, mock_rhr):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_bb.return_value = [{"most_recent": 55, "highest": 90, "lowest": 20}]
        mock_rhr.side_effect = Exception("RHR API down")

        api = _full_recovery_api()
        result = get_recovery_snapshot(api)

        assert result["resting_hr_yesterday"] is None
        assert result["hrv_last_night"] == 42

    @patch("garmin_mcp.tools.training.get_resting_hr_trend")
    @patch("garmin_mcp.tools.training.get_body_battery")
    @patch("garmin_mcp.tools.training.date")
    def test_readiness_failure_returns_none(
        self, mock_date, mock_bb, mock_rhr,
    ):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_bb.return_value = [{"most_recent": 55, "highest": 90, "lowest": 20}]
        mock_rhr.return_value = [{"date": "2025-01-14", "resting_hr": 58}]

        api = _full_recovery_api()
        api.get_training_readiness.side_effect = Exception("Readiness down")

        result = get_recovery_snapshot(api)

        assert result["readiness_score"] is None
        assert result["hrv_last_night"] == 42


# --- get_morning_readiness ---

class TestGetMorningReadiness:

    @patch("garmin_mcp.tools.training.date")
    def test_returns_morning_readiness(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_morning_training_readiness.return_value = {
            "score": 68,
            "level": "MODERATE",
            "sleepScorePercentage": 80,
            "recoveryTimeInHours": 18,
            "hrvStatus": "BALANCED",
            "heatAcclimationStatus": None,
            "altitudeAcclimationStatus": None,
        }

        result = get_morning_readiness(api, days=2)

        assert len(result) == 2
        assert result[0]["score"] == 68
        assert result[0]["level"] == "MODERATE"
        assert result[0]["hrv_status"] == "BALANCED"

    @patch("garmin_mcp.tools.training.date")
    def test_handles_none_response(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_morning_training_readiness.return_value = None

        result = get_morning_readiness(api, days=1)

        assert result[0]["score"] is None

    @patch("garmin_mcp.tools.training.date")
    def test_handles_exception(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_morning_training_readiness.side_effect = Exception("fail")

        result = get_morning_readiness(api, days=1)

        assert result[0]["score"] is None


# --- get_max_metrics ---

class TestGetMaxMetrics:

    @patch("garmin_mcp.tools.training.date")
    def test_returns_max_metrics(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_max_metrics.return_value = [{
            "calendarDate": "2025-01-15",
            "generic": {
                "vo2MaxPreciseValue": 52.3,
                "fitnessAge": 28,
            },
            "cycling": {
                "vo2MaxPreciseValue": 48.1,
            },
        }]

        result = get_max_metrics(api)

        assert result["vo2_max_running"] == 52.3
        assert result["fitness_age"] == 28
        assert result["vo2_max_cycling"] == 48.1
        assert result["updated"] == "2025-01-15"

    @patch("garmin_mcp.tools.training.date")
    def test_handles_empty_response(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_max_metrics.return_value = None

        result = get_max_metrics(api)

        assert result == {}

    @patch("garmin_mcp.tools.training.date")
    def test_handles_exception(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_max_metrics.side_effect = Exception("fail")

        result = get_max_metrics(api)

        assert result == {}


# --- get_endurance_score ---

class TestGetEnduranceScore:

    def test_returns_single_day_score(self):
        api = MagicMock()
        api.get_endurance_score.return_value = {
            "overallScore": 72,
            "runningScore": 68,
            "cyclingScore": 55,
            "swimmingScore": 30,
        }

        result = get_endurance_score(api, start_date="2025-01-15")

        assert result["overall_score"] == 72
        assert result["running_score"] == 68
        assert result["date"] == "2025-01-15"

    def test_returns_range_data(self):
        api = MagicMock()
        api.get_endurance_score.return_value = {"some": "aggregated_data"}

        result = get_endurance_score(
            api, start_date="2025-01-01", end_date="2025-01-15"
        )

        assert result == {"some": "aggregated_data"}
        api.get_endurance_score.assert_called_once_with("2025-01-01", "2025-01-15")

    def test_handles_exception(self):
        api = MagicMock()
        api.get_endurance_score.side_effect = Exception("fail")

        result = get_endurance_score(api, start_date="2025-01-15")

        assert result == {}


# --- get_lactate_threshold ---

class TestGetLactateThreshold:

    def test_returns_lactate_threshold(self):
        api = MagicMock()
        api.get_lactate_threshold.return_value = {
            "speed_and_heart_rate": {
                "heartRate": 165,
                "speed": 3.5,
                "calendarDate": "2025-01-10",
            },
            "power": {
                "functionalThresholdPower": 280,
            },
        }

        result = get_lactate_threshold(api)

        assert result["heart_rate_bpm"] == 165
        assert result["speed_m_per_s"] == 3.5
        assert result["pace_min_per_km"] is not None
        assert result["ftp_watts"] == 280
        assert result["date"] == "2025-01-10"

    def test_handles_empty_response(self):
        api = MagicMock()
        api.get_lactate_threshold.return_value = None

        result = get_lactate_threshold(api)

        assert result == {}

    def test_handles_exception(self):
        api = MagicMock()
        api.get_lactate_threshold.side_effect = Exception("fail")

        result = get_lactate_threshold(api)

        assert result == {}

    def test_pace_conversion_correct(self):
        api = MagicMock()
        # 3.333 m/s = 5:00 min/km
        api.get_lactate_threshold.return_value = {
            "speed_and_heart_rate": {
                "heartRate": 160,
                "speed": 3.333333,
                "calendarDate": "2025-01-10",
            },
            "power": {},
        }

        result = get_lactate_threshold(api)

        assert result["pace_min_per_km"] == "0:05:00"


# --- get_personal_records ---

class TestGetPersonalRecords:

    def test_returns_personal_records(self):
        api = MagicMock()
        api.get_personal_record.return_value = [
            {
                "typeKey": "running",
                "personalRecordType": "FASTEST_5K",
                "value": 1200.0,
                "activityId": "12345",
                "activityName": "Morning Run",
                "prStartTimeGMT": "2025-01-10T08:00:00",
            },
            {
                "typeKey": "running",
                "personalRecordType": "LONGEST_RUN",
                "value": 42195.0,
                "activityId": "67890",
                "activityName": "Marathon",
                "calendarDate": "2024-11-03",
            },
        ]

        result = get_personal_records(api)

        assert len(result) == 2
        assert result[0]["record_type"] == "FASTEST_5K"
        assert result[0]["value"] == 1200.0
        assert result[0]["activity_id"] == "12345"
        assert result[1]["record_type"] == "LONGEST_RUN"
        assert result[1]["date"] == "2024-11-03"

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_personal_record.return_value = None

        assert get_personal_records(api) == []

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_personal_record.side_effect = Exception("fail")

        assert get_personal_records(api) == []

    def test_handles_single_dict_response(self):
        api = MagicMock()
        api.get_personal_record.return_value = {
            "typeKey": "running",
            "personalRecordType": "FASTEST_MILE",
            "value": 360.0,
        }

        result = get_personal_records(api)

        assert len(result) == 1
        assert result[0]["record_type"] == "FASTEST_MILE"


# --- get_progress_summary ---

class TestGetProgressSummary:

    def test_returns_progress_data(self):
        api = MagicMock()
        api.get_progress_summary_between_dates.return_value = {
            "totalActivities": 25,
            "totalDistance": 120000,
            "totalDuration": 72000,
        }

        result = get_progress_summary(api, start_date="2025-01-01", end_date="2025-01-31")

        assert result["totalActivities"] == 25
        assert result["totalDistance"] == 120000
        api.get_progress_summary_between_dates.assert_called_once_with("2025-01-01", "2025-01-31")

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_progress_summary_between_dates.return_value = None

        assert get_progress_summary(api, start_date="2025-01-01", end_date="2025-01-31") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_progress_summary_between_dates.side_effect = Exception("fail")

        assert get_progress_summary(api, start_date="2025-01-01", end_date="2025-01-31") == {}
