"""Tests for garmin_mcp.tools.activities."""

from unittest.mock import MagicMock

from garmin_mcp.tools.activities import (
    _format_pace,
    _summarize_activity,
    get_activities_for_date,
    get_activities_in_range,
    get_activity_detail,
    get_activity_details,
    get_activity_gear,
    get_activity_power_zones,
    get_activity_split_summaries,
    get_activity_typed_splits,
    get_activity_weather,
    get_last_activity,
    get_recent_activities,
)

# --- _format_pace ---


class TestFormatPace:
    def test_converts_speed_to_pace(self):
        # 3.0 m/s => 1000/3 = 333.33s => 5:33/km
        assert _format_pace(3.0) == "5:33/km"

    def test_exactly_one_mps(self):
        # 1000/1 = 1000s => 16:40/km
        assert _format_pace(1.0) == "16:40/km"

    def test_returns_none_for_zero(self):
        assert _format_pace(0.0) is None

    def test_returns_none_for_negative(self):
        assert _format_pace(-1.0) is None

    def test_returns_none_for_none(self):
        assert _format_pace(None) is None


# --- _summarize_activity ---


def _sample_activity() -> dict:
    return {
        "activityId": 12345,
        "activityName": "Morning Run",
        "activityType": {"typeKey": "running"},
        "startTimeLocal": "2025-01-15 07:00:00",
        "distance": 5000.0,
        "duration": 1500.0,
        "averageHR": 155,
        "maxHR": 175,
        "averageSpeed": 3.333,
        "calories": 350,
        "elevationGain": 42.0,
    }


class TestSummarizeActivity:
    def test_extracts_all_fields(self):
        result = _summarize_activity(_sample_activity())
        assert result["activity_id"] == 12345
        assert result["name"] == "Morning Run"
        assert result["type"] == "running"
        assert result["date"] == "2025-01-15 07:00:00"
        assert result["distance_km"] == 5.0
        assert result["duration_seconds"] == 1500.0
        assert result["avg_hr"] == 155
        assert result["max_hr"] == 175
        assert result["avg_pace"] is not None
        assert result["calories"] == 350
        assert result["elevation_gain"] == 42.0

    def test_handles_missing_distance(self):
        act = _sample_activity()
        del act["distance"]
        result = _summarize_activity(act)
        assert result["distance_km"] is None

    def test_handles_missing_activity_type(self):
        act = _sample_activity()
        del act["activityType"]
        result = _summarize_activity(act)
        assert result["type"] is None


# --- get_recent_activities ---


class TestGetRecentActivities:
    def test_returns_summarized_activities(self):
        api = MagicMock()
        api.get_activities.return_value = [_sample_activity()]

        result = get_recent_activities(api, limit=5)

        assert len(result) == 1
        assert result[0]["activity_id"] == 12345
        api.get_activities.assert_called_once_with(
            0,
            5,
            activitytype=None,
        )

    def test_passes_activity_type_filter(self):
        api = MagicMock()
        api.get_activities.return_value = []

        get_recent_activities(api, limit=3, activity_type="running")

        api.get_activities.assert_called_once_with(
            0,
            3,
            activitytype="running",
        )

    def test_returns_empty_list_when_no_activities(self):
        api = MagicMock()
        api.get_activities.return_value = []

        assert get_recent_activities(api) == []

    def test_returns_empty_list_when_none(self):
        api = MagicMock()
        api.get_activities.return_value = None

        assert get_recent_activities(api) == []


# --- get_activity_detail ---


class TestGetActivityDetail:
    def test_returns_detail_with_laps_and_hr_zones(self):
        api = MagicMock()
        api.get_activity.return_value = _sample_activity()
        api.get_activity_splits.return_value = {
            "lapDTOs": [
                {
                    "lapIndex": 1,
                    "distance": 1000.0,
                    "duration": 300.0,
                    "averageHR": 150,
                    "maxHR": 165,
                    "averageSpeed": 3.333,
                    "calories": 70,
                }
            ]
        }
        api.get_activity_hr_in_timezones.return_value = [
            {
                "zones": [
                    {
                        "zoneNumber": 1,
                        "zoneLowBoundary": 100,
                        "zoneHighBoundary": 120,
                        "secsInZone": 60,
                    },
                    {
                        "zoneNumber": 2,
                        "zoneLowBoundary": 120,
                        "zoneHighBoundary": 140,
                        "secsInZone": 120,
                    },
                ]
            }
        ]

        result = get_activity_detail(api, "12345")

        assert result["activity_id"] == 12345
        assert len(result["laps"]) == 1
        assert result["laps"][0]["lap_number"] == 1
        assert result["laps"][0]["distance_km"] == 1.0
        assert len(result["hr_zones"]) == 2
        assert result["hr_zones"][0]["zone"] == 1

    def test_laps_empty_when_splits_fail(self):
        api = MagicMock()
        api.get_activity.return_value = _sample_activity()
        api.get_activity_splits.side_effect = Exception("api error")
        api.get_activity_hr_in_timezones.return_value = []

        result = get_activity_detail(api, "12345")

        assert result["laps"] == []

    def test_hr_zones_empty_when_fetch_fails(self):
        api = MagicMock()
        api.get_activity.return_value = _sample_activity()
        api.get_activity_splits.return_value = {"lapDTOs": []}
        api.get_activity_hr_in_timezones.side_effect = Exception("error")

        result = get_activity_detail(api, "12345")

        assert result["hr_zones"] == []

    def test_handles_none_splits_data(self):
        api = MagicMock()
        api.get_activity.return_value = _sample_activity()
        api.get_activity_splits.return_value = None
        api.get_activity_hr_in_timezones.return_value = None

        result = get_activity_detail(api, "12345")

        assert result["laps"] == []
        assert result["hr_zones"] == []


# --- get_activities_in_range ---


class TestGetActivitiesInRange:
    def test_returns_activities_in_date_range(self):
        api = MagicMock()
        api.get_activities_by_date.return_value = [_sample_activity()]

        result = get_activities_in_range(api, "2025-01-01", "2025-01-31")

        assert len(result) == 1
        api.get_activities_by_date.assert_called_once_with(
            "2025-01-01",
            "2025-01-31",
            activitytype=None,
        )

    def test_passes_activity_type(self):
        api = MagicMock()
        api.get_activities_by_date.return_value = []

        get_activities_in_range(api, "2025-01-01", "2025-01-31", activity_type="cycling")

        api.get_activities_by_date.assert_called_once_with(
            "2025-01-01",
            "2025-01-31",
            activitytype="cycling",
        )

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_activities_by_date.return_value = None

        assert get_activities_in_range(api, "2025-01-01", "2025-01-31") == []


# --- get_activity_typed_splits ---


class TestGetActivityTypedSplits:
    def test_returns_typed_splits(self):
        api = MagicMock()
        api.get_activity_typed_splits.return_value = {"splitType": "run_walk", "splits": []}

        result = get_activity_typed_splits(api, "12345")

        assert result["splitType"] == "run_walk"
        api.get_activity_typed_splits.assert_called_once_with("12345")

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_activity_typed_splits.return_value = None

        assert get_activity_typed_splits(api, "12345") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_activity_typed_splits.side_effect = Exception("fail")

        assert get_activity_typed_splits(api, "12345") == {}


# --- get_activity_split_summaries ---


class TestGetActivitySplitSummaries:
    def test_returns_split_summaries(self):
        api = MagicMock()
        api.get_activity_split_summaries.return_value = {"splits": [{"distance": 1000}]}

        result = get_activity_split_summaries(api, "12345")

        assert "splits" in result
        api.get_activity_split_summaries.assert_called_once_with("12345")

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_activity_split_summaries.return_value = None

        assert get_activity_split_summaries(api, "12345") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_activity_split_summaries.side_effect = Exception("fail")

        assert get_activity_split_summaries(api, "12345") == {}


# --- get_activity_weather ---


class TestGetActivityWeather:
    def test_returns_weather(self):
        api = MagicMock()
        api.get_activity_weather.return_value = {
            "temperature": 15.0,
            "humidity": 65,
            "windSpeed": 10.0,
        }

        result = get_activity_weather(api, "12345")

        assert result["temperature"] == 15.0
        assert result["humidity"] == 65

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_activity_weather.return_value = None

        assert get_activity_weather(api, "12345") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_activity_weather.side_effect = Exception("fail")

        assert get_activity_weather(api, "12345") == {}


# --- get_activity_power_zones ---


class TestGetActivityPowerZones:
    def test_returns_power_zones(self):
        api = MagicMock()
        api.get_activity_power_in_timezones.return_value = {"zones": [{"zone": 1, "secsInZone": 300}]}

        result = get_activity_power_zones(api, "12345")

        assert "zones" in result
        api.get_activity_power_in_timezones.assert_called_once_with("12345")

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_activity_power_in_timezones.return_value = None

        assert get_activity_power_zones(api, "12345") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_activity_power_in_timezones.side_effect = Exception("fail")

        assert get_activity_power_zones(api, "12345") == {}


# --- get_last_activity ---


class TestGetLastActivity:
    def test_returns_summarized_activity(self):
        api = MagicMock()
        api.get_last_activity.return_value = _sample_activity()

        result = get_last_activity(api)

        assert result["activity_id"] == 12345
        assert result["name"] == "Morning Run"
        api.get_last_activity.assert_called_once()

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_last_activity.return_value = None

        assert get_last_activity(api) == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_last_activity.side_effect = Exception("fail")

        assert get_last_activity(api) == {}


# --- get_activities_for_date ---


class TestGetActivitiesForDate:
    def test_returns_activities(self):
        api = MagicMock()
        api.get_activities_fordate.return_value = [_sample_activity()]

        result = get_activities_for_date(api, "2025-01-15")

        assert len(result) == 1
        assert result[0]["activity_id"] == 12345
        api.get_activities_fordate.assert_called_once_with("2025-01-15")

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_activities_fordate.return_value = None

        assert get_activities_for_date(api, "2025-01-15") == []

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_activities_fordate.side_effect = Exception("fail")

        assert get_activities_for_date(api, "2025-01-15") == []

    def test_wraps_single_dict_in_list(self):
        api = MagicMock()
        api.get_activities_fordate.return_value = _sample_activity()

        result = get_activities_for_date(api, "2025-01-15")

        assert len(result) == 1
        assert result[0]["activity_id"] == 12345


# --- get_activity_details ---


class TestGetActivityDetails:
    def test_returns_details(self):
        api = MagicMock()
        api.get_activity_details.return_value = {
            "activityId": 12345,
            "metricDescriptors": [],
            "activityDetailMetrics": [{"metricsIndex": 0}],
        }

        result = get_activity_details(api, "12345")

        assert result["activityId"] == 12345
        api.get_activity_details.assert_called_once_with("12345")

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_activity_details.return_value = None

        assert get_activity_details(api, "12345") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_activity_details.side_effect = Exception("fail")

        assert get_activity_details(api, "12345") == {}


# --- get_activity_gear ---


class TestGetActivityGear:
    def test_returns_gear(self):
        api = MagicMock()
        api.get_activity_gear.return_value = {
            "gearItems": [{"gearPk": 1, "displayName": "Nike Pegasus", "gearTypeName": "Running Shoe"}]
        }

        result = get_activity_gear(api, "12345")

        assert "gearItems" in result
        api.get_activity_gear.assert_called_once_with("12345")

    def test_returns_empty_on_none(self):
        api = MagicMock()
        api.get_activity_gear.return_value = None

        assert get_activity_gear(api, "12345") == {}

    def test_returns_empty_on_exception(self):
        api = MagicMock()
        api.get_activity_gear.side_effect = Exception("fail")

        assert get_activity_gear(api, "12345") == {}
