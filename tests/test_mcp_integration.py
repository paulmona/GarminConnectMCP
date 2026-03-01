"""Integration tests — exercise every MCP tool through the Streamable HTTP protocol.

These tests start the MCP server in-process via Starlette's TestClient and send
JSON-RPC requests to /mcp, validating the full round-trip: JSON-RPC → FastMCP
routing → tool function → call_with_retry → Garmin API mock → JSON response.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from garmin_mcp.server import mcp

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mcp_client():
    """Yield a TestClient wired to the MCP Streamable HTTP app.

    Enables json_response + stateless mode so responses come back as plain
    JSON (not SSE) and each request gets a fresh transport (no session state).
    Sends the MCP initialize handshake before yielding.
    """
    # Save originals
    orig_json = mcp.settings.json_response
    orig_stateless = mcp.settings.stateless_http

    mcp.settings.json_response = True
    mcp.settings.stateless_http = True
    mcp._session_manager = None  # force fresh session manager

    app = mcp.streamable_http_app()

    with TestClient(
        app,
        headers={
            "Host": "localhost:80",
            "Accept": "application/json, text/event-stream",
        },
    ) as client:
        # MCP initialize handshake
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "integration-test", "version": "1.0"},
                },
            },
        )
        assert resp.status_code == 200
        yield client

    # Restore
    mcp.settings.json_response = orig_json
    mcp.settings.stateless_http = orig_stateless
    mcp._session_manager = None


@pytest.fixture()
def mock_api():
    """Patch _get_client so call_with_retry delegates to a mock Garmin API."""
    api = MagicMock()
    client = MagicMock()
    client.call_with_retry.side_effect = lambda fn: fn(api)

    with patch("garmin_mcp.server._get_client", return_value=client):
        yield api


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQ_ID = 0


def _call_tool(client: TestClient, name: str, arguments: dict | None = None):
    """Send a tools/call JSON-RPC request and return the parsed tool output."""
    global _REQ_ID
    _REQ_ID += 1
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": _REQ_ID,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "result" in body, f"No result in response: {body}"
    text = body["result"]["content"][0]["text"]
    return json.loads(text)


# ---------------------------------------------------------------------------
# Protocol-level tests
# ---------------------------------------------------------------------------


class TestMcpProtocol:
    def test_initialize(self, mcp_client):
        """Initialize was already called by the fixture; verify it worked."""
        # Just call list tools to confirm the session is alive
        resp = mcp_client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 999,
                "method": "tools/list",
                "params": {},
            },
        )
        assert resp.status_code == 200

    def test_list_tools_count(self, mcp_client):
        resp = mcp_client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 998,
                "method": "tools/list",
                "params": {},
            },
        )
        tools = resp.json()["result"]["tools"]
        assert len(tools) == 42

    def test_list_tools_names(self, mcp_client):
        resp = mcp_client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 997,
                "method": "tools/list",
                "params": {},
            },
        )
        names = {t["name"] for t in resp.json()["result"]["tools"]}
        assert "get_recent_activities" in names
        assert "get_last_activity" in names
        assert "upload_cycling_workout" in names


# ---------------------------------------------------------------------------
# Input validation through MCP
# ---------------------------------------------------------------------------


class TestMcpInputValidation:
    def test_invalid_date_returns_error(self, mcp_client, mock_api):
        resp = mcp_client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 900,
                "method": "tools/call",
                "params": {"name": "get_daily_stats", "arguments": {"cdate": "not-a-date"}},
            },
        )
        body = resp.json()
        assert body["result"]["isError"] is True

    def test_invalid_activity_id_returns_error(self, mcp_client, mock_api):
        resp = mcp_client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 901,
                "method": "tools/call",
                "params": {"name": "get_activity_detail", "arguments": {"activity_id": "abc; DROP TABLE"}},
            },
        )
        body = resp.json()
        assert body["result"]["isError"] is True

    def test_not_configured_error(self, mcp_client):
        from garmin_mcp.config import CredentialsNotConfiguredError

        client_mock = MagicMock()
        client_mock.call_with_retry.side_effect = CredentialsNotConfiguredError("missing")

        with patch("garmin_mcp.server._get_client", return_value=client_mock):
            result = _call_tool(mcp_client, "get_training_status")
            assert result["error"] == "not_configured"


# ---------------------------------------------------------------------------
# Activity tools
# ---------------------------------------------------------------------------

_SAMPLE_ACTIVITY = {
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


class TestActivityTools:
    def test_get_recent_activities(self, mcp_client, mock_api):
        mock_api.get_activities.return_value = [_SAMPLE_ACTIVITY]
        result = _call_tool(mcp_client, "get_recent_activities", {"limit": 5})
        assert isinstance(result, list)
        assert result[0]["activity_id"] == 12345

    def test_get_last_activity(self, mcp_client, mock_api):
        mock_api.get_last_activity.return_value = _SAMPLE_ACTIVITY
        result = _call_tool(mcp_client, "get_last_activity")
        assert result["activity_id"] == 12345
        assert result["name"] == "Morning Run"

    def test_get_activities_for_date(self, mcp_client, mock_api):
        mock_api.get_activities_fordate.return_value = [_SAMPLE_ACTIVITY]
        result = _call_tool(mcp_client, "get_activities_for_date", {"cdate": "2025-01-15"})
        assert isinstance(result, list)
        assert result[0]["activity_id"] == 12345

    def test_get_activities_in_range(self, mcp_client, mock_api):
        mock_api.get_activities_by_date.return_value = [_SAMPLE_ACTIVITY]
        result = _call_tool(
            mcp_client,
            "get_activities_in_range",
            {
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
            },
        )
        assert isinstance(result, list)
        assert len(result) == 1

    def test_get_activity_detail(self, mcp_client, mock_api):
        mock_api.get_activity.return_value = _SAMPLE_ACTIVITY
        mock_api.get_activity_splits.return_value = {"lapDTOs": []}
        mock_api.get_activity_hr_in_timezones.return_value = []
        result = _call_tool(mcp_client, "get_activity_detail", {"activity_id": "12345"})
        assert result["activity_id"] == 12345

    def test_get_activity_details(self, mcp_client, mock_api):
        mock_api.get_activity_details.return_value = {"activityId": 12345, "metrics": []}
        result = _call_tool(mcp_client, "get_activity_details", {"activity_id": "12345"})
        assert result["activityId"] == 12345

    def test_get_activity_gear(self, mcp_client, mock_api):
        mock_api.get_activity_gear.return_value = {"gearItems": [{"displayName": "Pegasus"}]}
        result = _call_tool(mcp_client, "get_activity_gear", {"activity_id": "12345"})
        assert "gearItems" in result

    def test_get_activity_typed_splits(self, mcp_client, mock_api):
        mock_api.get_activity_typed_splits.return_value = {"splitType": "run_walk"}
        result = _call_tool(mcp_client, "get_activity_typed_splits", {"activity_id": "12345"})
        assert result["splitType"] == "run_walk"

    def test_get_activity_split_summaries(self, mcp_client, mock_api):
        mock_api.get_activity_split_summaries.return_value = {"splits": []}
        result = _call_tool(mcp_client, "get_activity_split_summaries", {"activity_id": "12345"})
        assert "splits" in result

    def test_get_activity_weather(self, mcp_client, mock_api):
        mock_api.get_activity_weather.return_value = {"temperature": 15.0}
        result = _call_tool(mcp_client, "get_activity_weather", {"activity_id": "12345"})
        assert result["temperature"] == 15.0

    def test_get_activity_power_zones(self, mcp_client, mock_api):
        mock_api.get_activity_power_in_timezones.return_value = {"zones": []}
        result = _call_tool(mcp_client, "get_activity_power_zones", {"activity_id": "12345"})
        assert "zones" in result


# ---------------------------------------------------------------------------
# Health tools
# ---------------------------------------------------------------------------


class TestHealthTools:
    def test_get_hrv_trend(self, mcp_client, mock_api):
        mock_api.get_hrv_data.return_value = {
            "hrvSummary": {"weeklyAvg": 45, "lastNightAvg": 40},
        }
        result = _call_tool(mcp_client, "get_hrv_trend", {"days": 3})
        assert result["days_requested"] == 3
        assert isinstance(result["daily"], list)

    def test_get_sleep_history(self, mcp_client, mock_api):
        mock_api.get_sleep_data.return_value = {
            "dailySleepDTO": {
                "sleepScores": {"overall": {"value": 85}},
                "sleepTimeSeconds": 28800,
                "deepSleepSeconds": 7200,
                "lightSleepSeconds": 14400,
                "remSleepSeconds": 5400,
                "awakeSleepSeconds": 1800,
            },
        }
        result = _call_tool(mcp_client, "get_sleep_history", {"days": 2})
        assert isinstance(result, list)

    def test_get_body_battery(self, mcp_client, mock_api):
        mock_api.get_body_battery.return_value = [
            {
                "calendarDate": "2025-01-07",
                "charged": 40,
                "drained": 60,
                "bodyBatteryHighestValue": 90,
                "bodyBatteryLowestValue": 20,
                "bodyBatteryMostRecentValue": 55,
            }
        ]
        result = _call_tool(mcp_client, "get_body_battery", {"days": 3})
        assert isinstance(result, list)

    def test_get_resting_hr_trend(self, mcp_client, mock_api):
        mock_api.get_rhr_day.return_value = {
            "allMetrics": {
                "metricsMap": {
                    "WELLNESS_RESTING_HEART_RATE": [{"value": 58.0}],
                }
            },
        }
        result = _call_tool(mcp_client, "get_resting_hr_trend", {"days": 3})
        assert isinstance(result, list)

    def test_get_stress_data(self, mcp_client, mock_api):
        mock_api.get_all_day_stress.return_value = {
            "overallStressLevel": 35,
            "stressQualifier": "low",
        }
        result = _call_tool(mcp_client, "get_stress_data", {"days": 2})
        assert isinstance(result, list)

    def test_get_daily_stats(self, mcp_client, mock_api):
        mock_api.get_stats.return_value = {"totalSteps": 8500}
        result = _call_tool(mcp_client, "get_daily_stats", {"cdate": "2025-01-15"})
        assert result["totalSteps"] == 8500

    def test_get_heart_rates(self, mcp_client, mock_api):
        mock_api.get_heart_rates.return_value = {
            "restingHeartRate": 58,
            "maxHeartRate": 175,
            "minHeartRate": 45,
        }
        result = _call_tool(mcp_client, "get_heart_rates", {"cdate": "2025-01-15"})
        assert result["resting_hr"] == 58

    def test_get_body_battery_events(self, mcp_client, mock_api):
        mock_api.get_body_battery_events.return_value = [
            {
                "eventType": "ACTIVITY",
                "title": "Run",
                "impact": "HIGH",
                "durationInSeconds": 3600,
                "bodyBatteryChange": -25,
            },
        ]
        result = _call_tool(mcp_client, "get_body_battery_events", {"cdate": "2025-01-15"})
        assert result["date"] == "2025-01-15"
        assert len(result["events"]) == 1

    def test_get_intensity_minutes(self, mcp_client, mock_api):
        mock_api.get_intensity_minutes_data.return_value = {
            "weeklyGoal": 150,
            "moderateIntensityMinutes": 80,
            "vigorousIntensityMinutes": 40,
        }
        result = _call_tool(mcp_client, "get_intensity_minutes", {"cdate": "2025-01-15"})
        assert result["weekly_goal"] == 150

    def test_get_respiration_data(self, mcp_client, mock_api):
        mock_api.get_respiration_data.return_value = {
            "avgWakingRespirationValue": 16.0,
            "highestRespirationValue": 22.0,
        }
        result = _call_tool(mcp_client, "get_respiration_data", {"cdate": "2025-01-15"})
        assert result["avgWakingRespirationValue"] == 16.0

    def test_get_spo2_data(self, mcp_client, mock_api):
        mock_api.get_spo2_data.return_value = {
            "calendarDate": "2025-01-15",
            "averageSPO2": 96.0,
        }
        result = _call_tool(mcp_client, "get_spo2_data", {"cdate": "2025-01-15"})
        assert result["averageSPO2"] == 96.0

    def test_get_weekly_stress(self, mcp_client, mock_api):
        mock_api.get_weekly_stress.return_value = {"weeks": [{"avg": 35}]}
        result = _call_tool(mcp_client, "get_weekly_stress", {"end": "2025-01-15"})
        assert "weeks" in result

    def test_get_weekly_intensity_minutes(self, mcp_client, mock_api):
        mock_api.get_weekly_intensity_minutes.return_value = {"weeks": [{"total": 150}]}
        result = _call_tool(mcp_client, "get_weekly_intensity_minutes", {"end": "2025-01-15"})
        assert "weeks" in result


# ---------------------------------------------------------------------------
# Training tools
# ---------------------------------------------------------------------------


class TestTrainingTools:
    def test_get_training_status(self, mcp_client, mock_api):
        mock_api.get_training_status.return_value = {
            "trainingStatusLabel": "PRODUCTIVE",
            "vo2Max": 52.0,
        }
        mock_api.get_training_readiness.return_value = [{"score": 75, "level": "GOOD"}]
        result = _call_tool(mcp_client, "get_training_status")
        assert result["training_status"] == "PRODUCTIVE"

    def test_get_race_predictions(self, mcp_client, mock_api):
        mock_api.get_race_predictions.return_value = [
            {"racePredictionType": "5K", "predictedTime": 1200.0},
        ]
        result = _call_tool(mcp_client, "get_race_predictions")
        assert "5K" in result

    def test_get_weekly_summary(self, mcp_client, mock_api):
        mock_api.get_activities_by_date.return_value = [_SAMPLE_ACTIVITY]
        mock_api.get_rhr_day.return_value = None
        mock_api.get_sleep_data.return_value = None
        result = _call_tool(mcp_client, "get_weekly_summary")
        assert "total_activities" in result

    def test_get_recovery_snapshot(self, mcp_client, mock_api):
        mock_api.get_hrv_data.return_value = {
            "hrvSummary": {"lastNight": 42, "lastNightAvg": 40, "status": "BALANCED"},
        }
        mock_api.get_sleep_data.return_value = {
            "dailySleepDTO": {
                "sleepScores": {"overall": {"value": 80}},
                "sleepTimeSeconds": 28800,
            },
        }
        mock_api.get_body_battery.return_value = [
            {
                "bodyBatteryMostRecentValue": 60,
                "bodyBatteryHighestValue": 90,
                "bodyBatteryLowestValue": 20,
            }
        ]
        mock_api.get_rhr_day.return_value = None
        mock_api.get_training_readiness.return_value = [{"score": 75, "level": "GOOD"}]
        result = _call_tool(mcp_client, "get_recovery_snapshot")
        assert "hrv_last_night" in result

    def test_get_morning_readiness(self, mcp_client, mock_api):
        mock_api.get_morning_training_readiness.return_value = {
            "score": 80,
            "level": "GOOD",
        }
        result = _call_tool(mcp_client, "get_morning_readiness", {"days": 3})
        assert isinstance(result, list)

    def test_get_max_metrics(self, mcp_client, mock_api):
        mock_api.get_max_metrics.return_value = {
            "generic": {"vo2MaxPreciseValue": 52.5, "fitnessAge": 28},
            "cycling": {"vo2MaxPreciseValue": 48.0},
            "calendarDate": "2025-01-15",
        }
        result = _call_tool(mcp_client, "get_max_metrics")
        assert result["vo2_max_running"] == 52.5

    def test_get_endurance_score(self, mcp_client, mock_api):
        mock_api.get_endurance_score.return_value = {
            "overallScore": 75,
            "runningScore": 80,
        }
        result = _call_tool(mcp_client, "get_endurance_score")
        assert result["overall_score"] == 75

    def test_get_lactate_threshold(self, mcp_client, mock_api):
        mock_api.get_lactate_threshold.return_value = {
            "speed_and_heart_rate": {
                "heartRate": 170,
                "speed": 4.0,
                "calendarDate": "2025-01-15",
            },
        }
        result = _call_tool(mcp_client, "get_lactate_threshold")
        assert result["heart_rate_bpm"] == 170

    def test_get_fitness_age(self, mcp_client, mock_api):
        mock_api.get_fitnessage_data.return_value = {
            "fitnessAge": 28,
            "chronologicalAge": 35,
        }
        result = _call_tool(mcp_client, "get_fitness_age", {"cdate": "2025-01-15"})
        assert result["fitnessAge"] == 28

    def test_get_progress_summary(self, mcp_client, mock_api):
        mock_api.get_progress_summary_between_dates.return_value = {
            "totalActivities": 20,
            "totalDistance": 100000,
        }
        result = _call_tool(
            mcp_client,
            "get_progress_summary",
            {
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
            },
        )
        assert result["totalActivities"] == 20

    def test_get_personal_records(self, mcp_client, mock_api):
        mock_api.get_personal_record.return_value = [
            {"typeKey": "running", "personalRecordType": "FASTEST_5K", "value": 1200},
        ]
        result = _call_tool(mcp_client, "get_personal_records")
        assert isinstance(result, list)
        assert result[0]["record_type"] == "FASTEST_5K"


# ---------------------------------------------------------------------------
# Body tools
# ---------------------------------------------------------------------------


class TestBodyTools:
    def test_get_weight_trend(self, mcp_client, mock_api):
        mock_api.get_weigh_ins.return_value = {
            "dailyWeightSummaries": [
                {"calendarDate": "2025-01-15", "weight": 75000, "bmi": 23.5},
            ],
        }
        result = _call_tool(mcp_client, "get_weight_trend", {"days": 7})
        assert result["days_requested"] == 7
        assert len(result["entries"]) == 1

    def test_get_body_composition(self, mcp_client, mock_api):
        mock_api.get_body_composition.return_value = {
            "totalAverage": {"weight": 75000, "bmi": 23.5, "bodyFat": 18.0},
            "dateWeightList": [
                {"calendarDate": "2025-01-15", "weight": 75000, "bmi": 23.5, "bodyFat": 18.0},
            ],
        }
        result = _call_tool(mcp_client, "get_body_composition", {"days": 7})
        assert result["days_requested"] == 7


# ---------------------------------------------------------------------------
# Workout tools
# ---------------------------------------------------------------------------


class TestWorkoutTools:
    def test_get_workouts(self, mcp_client, mock_api):
        mock_api.get_workouts.return_value = [
            {"workoutId": 111, "workoutName": "Easy Run", "sportType": {"sportTypeKey": "running"}},
        ]
        result = _call_tool(mcp_client, "get_workouts")
        assert isinstance(result, list)
        assert result[0]["workout_id"] == 111

    def test_get_workout_by_id(self, mcp_client, mock_api):
        mock_api.get_workout_by_id.return_value = {
            "workoutId": 111,
            "workoutName": "Easy Run",
        }
        result = _call_tool(mcp_client, "get_workout_by_id", {"workout_id": "111"})
        assert result["workoutId"] == 111

    def test_get_training_plans(self, mcp_client, mock_api):
        mock_api.get_training_plans.return_value = [
            {"planName": "5K Beginner", "status": "ACTIVE"},
        ]
        result = _call_tool(mcp_client, "get_training_plans")
        assert isinstance(result, list)

    def test_upload_running_workout(self, mcp_client, mock_api):
        mock_api.upload_running_workout.return_value = {"workoutId": 999}
        result = _call_tool(
            mcp_client,
            "upload_running_workout",
            {
                "workout_name": "Test Run",
                "steps": [
                    {"type": "warmup", "duration_seconds": 300},
                    {"type": "interval", "duration_seconds": 600},
                    {"type": "cooldown", "duration_seconds": 300},
                ],
            },
        )
        assert result["workoutId"] == 999

    def test_upload_cycling_workout(self, mcp_client, mock_api):
        mock_api.upload_cycling_workout.return_value = {"workoutId": 888}
        result = _call_tool(
            mcp_client,
            "upload_cycling_workout",
            {
                "workout_name": "FTP Test",
                "steps": [
                    {"type": "warmup", "duration_seconds": 600},
                    {"type": "interval", "duration_seconds": 1200},
                    {"type": "cooldown", "duration_seconds": 300},
                ],
            },
        )
        assert result["workoutId"] == 888
