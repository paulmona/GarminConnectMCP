"""Tests for garmin_mcp.tools.health."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from garmin_mcp.tools.health import (
    _date_range,
    get_body_battery,
    get_hrv_trend,
    get_resting_hr_trend,
    get_sleep_history,
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
