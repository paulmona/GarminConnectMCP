"""Tests for garmin_mcp.tools.health."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from garmin_mcp.tools.health import (
    _date_range,
    get_body_battery,
    get_body_battery_events,
    get_daily_stats,
    get_heart_rates,
    get_hrv_trend,
    get_intensity_minutes,
    get_resting_hr_trend,
    get_sleep_history,
    get_stress_data,
    get_weekly_intensity_minutes,
    get_weekly_stress,
)


# --- _date_range ---

class TestDateRange:

    @patch("garmin_mcp.tools.health.date")
    def test_returns_correct_number_of_dates(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        result = _date_range(3)
        assert len(result) == 3

    @patch("garmin_mcp.tools.health.date")
    def test_dates_are_most_recent_first(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        result = _date_range(3)
        assert result == ["2025-01-15", "2025-01-14", "2025-01-13"]

    @patch("garmin_mcp.tools.health.date")
    def test_single_day(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 1)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        result = _date_range(1)
        assert result == ["2025-01-01"]


# --- get_hrv_trend ---

class TestGetHrvTrend:

    @patch("garmin_mcp.tools.health._date_range")
    def test_returns_hrv_data(self, mock_range):
        mock_range.return_value = ["2025-01-03", "2025-01-02", "2025-01-01"]
        api = MagicMock()
        api.get_hrv_data.return_value = {
            "hrvSummary": {
                "weeklyAvg": 45,
                "lastNight": 42,
                "lastNightAvg": 40,
                "lastNight5MinHigh": 55,
                "baselineLowUpper": 30,
                "baselineBalancedLow": 35,
                "baselineBalancedUpper": 50,
                "status": "BALANCED",
            }
        }

        result = get_hrv_trend(api, days=3)

        assert result["days_requested"] == 3
        assert len(result["daily"]) == 3

    @patch("garmin_mcp.tools.health._date_range")
    def test_handles_missing_hrv_data(self, mock_range):
        mock_range.return_value = ["2025-01-01"]
        api = MagicMock()
        api.get_hrv_data.return_value = None

        result = get_hrv_trend(api, days=1)

        assert result["daily"][0]["weekly_avg"] is None

    @patch("garmin_mcp.tools.health._date_range")
    def test_handles_api_exception(self, mock_range):
        mock_range.return_value = ["2025-01-01"]
        api = MagicMock()
        api.get_hrv_data.side_effect = Exception("API error")

        result = get_hrv_trend(api, days=1)

        assert result["daily"][0]["weekly_avg"] is None

    @patch("garmin_mcp.tools.health._date_range")
    def test_rolling_avg_calculated_with_enough_data(self, mock_range):
        dates = [f"2025-01-{i:02d}" for i in range(10, 0, -1)]
        mock_range.return_value = dates
        api = MagicMock()

        # Return data with last_night_avg values
        api.get_hrv_data.return_value = {
            "hrvSummary": {
                "lastNightAvg": 40,
                "weeklyAvg": 42,
            }
        }

        result = get_hrv_trend(api, days=10)

        assert result["rolling_avg_7d"] == 40.0

    @patch("garmin_mcp.tools.health._date_range")
    def test_rolling_avg_none_with_insufficient_data(self, mock_range):
        mock_range.return_value = ["2025-01-03", "2025-01-02", "2025-01-01"]
        api = MagicMock()
        api.get_hrv_data.return_value = {
            "hrvSummary": {"lastNightAvg": 40}
        }

        result = get_hrv_trend(api, days=3)

        assert result["rolling_avg_7d"] is None


# --- get_sleep_history ---

class TestGetSleepHistory:

    @patch("garmin_mcp.tools.health._date_range")
    def test_returns_sleep_data(self, mock_range):
        mock_range.return_value = ["2025-01-02", "2025-01-01"]
        api = MagicMock()
        api.get_sleep_data.return_value = {
            "dailySleepDTO": {
                "sleepScores": {"overall": {"value": 85}},
                "sleepTimeSeconds": 28800,
                "deepSleepSeconds": 7200,
                "lightSleepSeconds": 14400,
                "remSleepSeconds": 5400,
                "awakeSleepSeconds": 1800,
            }
        }

        result = get_sleep_history(api, days=2)

        assert len(result) == 2
        assert result[0]["sleep_score"] == 85
        assert result[0]["total_sleep_seconds"] == 28800

    @patch("garmin_mcp.tools.health._date_range")
    def test_handles_none_sleep_data(self, mock_range):
        mock_range.return_value = ["2025-01-01"]
        api = MagicMock()
        api.get_sleep_data.return_value = None

        result = get_sleep_history(api, days=1)

        assert result[0]["sleep_score"] is None

    @patch("garmin_mcp.tools.health._date_range")
    def test_handles_exception(self, mock_range):
        mock_range.return_value = ["2025-01-01"]
        api = MagicMock()
        api.get_sleep_data.side_effect = Exception("error")

        result = get_sleep_history(api, days=1)

        assert result[0]["sleep_score"] is None


# --- get_body_battery ---

class TestGetBodyBattery:

    @patch("garmin_mcp.tools.health.date")
    def test_returns_body_battery_data(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 7)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_body_battery.return_value = [
            {
                "calendarDate": "2025-01-07",
                "charged": 40,
                "drained": 60,
                "startTimestampGMT": 75,
                "endTimestampGMT": 55,
                "bodyBatteryHighestValue": 90,
                "bodyBatteryLowestValue": 20,
                "bodyBatteryMostRecentValue": 55,
            }
        ]

        result = get_body_battery(api, days=7)

        assert len(result) == 1
        assert result[0]["date"] == "2025-01-07"
        assert result[0]["highest"] == 90

    @patch("garmin_mcp.tools.health.date")
    def test_returns_empty_on_exception(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 7)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_body_battery.side_effect = Exception("error")

        assert get_body_battery(api) == []

    @patch("garmin_mcp.tools.health.date")
    def test_returns_empty_on_none_data(self, mock_date):
        mock_date.today.return_value = date(2025, 1, 7)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        api = MagicMock()
        api.get_body_battery.return_value = None

        assert get_body_battery(api) == []


# --- get_resting_hr_trend ---

class TestGetRestingHrTrend:

    @patch("garmin_mcp.tools.health._date_range")
    def test_returns_rhr_values(self, mock_range):
        mock_range.return_value = ["2025-01-02", "2025-01-01"]
        api = MagicMock()
        api.get_rhr_day.return_value = {
            "allMetrics": {
                "metricsMap": {
                    "WELLNESS_RESTING_HEART_RATE": [{"value": 58.0, "calendarDate": "2025-01-02"}]
                }
            }
        }

        result = get_resting_hr_trend(api, days=2)

        assert len(result) == 2
        assert result[0]["resting_hr"] == 58

    @patch("garmin_mcp.tools.health._date_range")
    def test_handles_empty_rhr_metrics(self, mock_range):
        mock_range.return_value = ["2025-01-01"]
        api = MagicMock()
        api.get_rhr_day.return_value = {
            "allMetrics": {"metricsMap": {"WELLNESS_RESTING_HEART_RATE": []}}
        }

        result = get_resting_hr_trend(api, days=1)

        assert result[0]["resting_hr"] is None

    @patch("garmin_mcp.tools.health._date_range")
    def test_handles_none_rhr_data(self, mock_range):
        mock_range.return_value = ["2025-01-01"]
        api = MagicMock()
        api.get_rhr_day.return_value = None

        result = get_resting_hr_trend(api, days=1)

        assert result[0]["resting_hr"] is None

    @patch("garmin_mcp.tools.health._date_range")
    def test_handles_exception(self, mock_range):
        mock_range.return_value = ["2025-01-01"]
        api = MagicMock()
        api.get_rhr_day.side_effect = Exception("api fail")

        result = get_resting_hr_trend(api, days=1)

        assert result[0]["resting_hr"] is None


# --- get_stress_data ---

class TestGetStressData:

    @patch("garmin_mcp.tools.health._date_range")
    def test_returns_stress_data(self, mock_range):
        mock_range.return_value = ["2025-01-02", "2025-01-01"]
        api = MagicMock()
        api.get_all_day_stress.return_value = {
            "overallStressLevel": 35,
            "restStressDuration": 28800,
            "activityStressDuration": 3600,
            "uncategorizedStressDuration": 1200,
            "totalStressDuration": 43200,
            "lowStressDuration": 25000,
            "mediumStressDuration": 10000,
            "highStressDuration": 5000,
            "stressQualifier": "low",
        }

        result = get_stress_data(api, days=2)

        assert len(result) == 2
        assert result[0]["overall_stress_level"] == 35
        assert result[0]["stress_qualifier"] == "low"
        assert result[0]["high_stress_duration"] == 5000

    @patch("garmin_mcp.tools.health._date_range")
    def test_handles_none_stress_data(self, mock_range):
        mock_range.return_value = ["2025-01-01"]
        api = MagicMock()
        api.get_all_day_stress.return_value = None

        result = get_stress_data(api, days=1)

        assert result[0]["overall_stress_level"] is None

    @patch("garmin_mcp.tools.health._date_range")
    def test_handles_exception(self, mock_range):
        mock_range.return_value = ["2025-01-01"]
        api = MagicMock()
        api.get_all_day_stress.side_effect = Exception("api fail")

        result = get_stress_data(api, days=1)

        assert result[0]["overall_stress_level"] is None


# --- get_intensity_minutes ---

class TestGetIntensityMinutes:

    def test_returns_intensity_minutes(self):
        api = MagicMock()
        api.get_intensity_minutes_data.return_value = {
            "weeklyGoal": 150,
            "moderateIntensityMinutes": 80,
            "vigorousIntensityMinutes": 40,
            "intensityMinutesGoalReached": 160,
        }

        result = get_intensity_minutes(api, cdate="2025-01-15")

        assert result["date"] == "2025-01-15"
        assert result["weekly_goal"] == 150
        assert result["moderate_minutes"] == 80
        assert result["vigorous_minutes"] == 40
        assert result["total_intensity_minutes"] == 160

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_intensity_minutes_data.return_value = None

        assert get_intensity_minutes(api, cdate="2025-01-15") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_intensity_minutes_data.side_effect = Exception("fail")

        assert get_intensity_minutes(api, cdate="2025-01-15") == {}


# --- get_body_battery_events ---

class TestGetBodyBatteryEvents:

    def test_returns_events(self):
        api = MagicMock()
        api.get_body_battery_events.return_value = [
            {
                "eventType": "ACTIVITY",
                "title": "Morning Run",
                "impact": "HIGH",
                "durationInSeconds": 3600,
                "bodyBatteryChange": -25,
            },
            {
                "eventType": "SLEEP",
                "title": "Night Sleep",
                "impact": "POSITIVE",
                "durationInSeconds": 28800,
                "bodyBatteryChange": 45,
            },
        ]

        result = get_body_battery_events(api, cdate="2025-01-15")

        assert result["date"] == "2025-01-15"
        assert len(result["events"]) == 2
        assert result["events"][0]["event_type"] == "ACTIVITY"
        assert result["events"][0]["body_battery_change"] == -25
        assert result["events"][1]["event_type"] == "SLEEP"

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_body_battery_events.return_value = None

        assert get_body_battery_events(api, cdate="2025-01-15") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_body_battery_events.side_effect = Exception("fail")

        assert get_body_battery_events(api, cdate="2025-01-15") == {}


# --- get_heart_rates ---

class TestGetHeartRates:

    def test_returns_heart_rate_data(self):
        api = MagicMock()
        api.get_heart_rates.return_value = {
            "restingHeartRate": 58,
            "maxHeartRate": 175,
            "minHeartRate": 45,
            "heartRateZones": [
                {"zoneNumber": 1, "secsInZone": 50000, "zoneLowBoundary": 50},
                {"zoneNumber": 2, "secsInZone": 10000, "zoneLowBoundary": 100},
            ],
        }

        result = get_heart_rates(api, cdate="2025-01-15")

        assert result["date"] == "2025-01-15"
        assert result["resting_hr"] == 58
        assert result["max_hr"] == 175
        assert result["min_hr"] == 45
        assert len(result["heart_rate_zones"]) == 2
        assert result["heart_rate_zones"][0]["zone_number"] == 1

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_heart_rates.return_value = None

        assert get_heart_rates(api, cdate="2025-01-15") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_heart_rates.side_effect = Exception("fail")

        assert get_heart_rates(api, cdate="2025-01-15") == {}

    def test_handles_missing_zones(self):
        api = MagicMock()
        api.get_heart_rates.return_value = {
            "restingHeartRate": 60,
            "maxHeartRate": 150,
            "minHeartRate": 48,
        }

        result = get_heart_rates(api, cdate="2025-01-15")

        assert result["resting_hr"] == 60
        assert "heart_rate_zones" not in result


# --- get_daily_stats ---

class TestGetDailyStats:

    def test_returns_stats(self):
        api = MagicMock()
        api.get_stats.return_value = {
            "totalSteps": 8500,
            "totalDistanceMeters": 6200,
            "activeSeconds": 3600,
        }

        result = get_daily_stats(api, cdate="2025-01-15")

        assert result["totalSteps"] == 8500
        api.get_stats.assert_called_once_with("2025-01-15")

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_stats.return_value = None

        assert get_daily_stats(api, cdate="2025-01-15") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_stats.side_effect = Exception("fail")

        assert get_daily_stats(api, cdate="2025-01-15") == {}


# --- get_weekly_stress ---

class TestGetWeeklyStress:

    def test_returns_weekly_stress(self):
        api = MagicMock()
        api.get_weekly_stress.return_value = {"weeks": [{"avg": 35}]}

        result = get_weekly_stress(api, end="2025-01-15", weeks=4)

        assert result["weeks"][0]["avg"] == 35
        api.get_weekly_stress.assert_called_once_with("2025-01-15", 4)

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_weekly_stress.return_value = None

        assert get_weekly_stress(api, end="2025-01-15") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_weekly_stress.side_effect = Exception("fail")

        assert get_weekly_stress(api, end="2025-01-15") == {}


# --- get_weekly_intensity_minutes ---

class TestGetWeeklyIntensityMinutes:

    def test_returns_weekly_data(self):
        api = MagicMock()
        api.get_weekly_intensity_minutes.return_value = {"weeks": [{"total": 150}]}

        result = get_weekly_intensity_minutes(api, end="2025-01-15", weeks=4)

        assert result["weeks"][0]["total"] == 150
        api.get_weekly_intensity_minutes.assert_called_once_with("2025-01-15", 4)

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_weekly_intensity_minutes.return_value = None

        assert get_weekly_intensity_minutes(api, end="2025-01-15") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_weekly_intensity_minutes.side_effect = Exception("fail")

        assert get_weekly_intensity_minutes(api, end="2025-01-15") == {}
