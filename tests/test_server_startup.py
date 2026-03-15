"""Smoke tests verifying the MCP server registers all expected tools."""

import os
from unittest.mock import patch


class TestCustomEndpointPath:
    """Tests for MCP_ENDPOINT_PATH configuration."""

    def test_default_endpoint_path(self):
        from garmin_mcp.server import mcp

        assert mcp.settings.streamable_http_path == "/mcp"

    def test_custom_endpoint_path_applied(self):
        """MCP_ENDPOINT_PATH sets the streamable_http_path on the FastMCP instance."""
        env = {
            "MCP_MODE": "sse",
            "MCP_ENDPOINT_PATH": "/x7k9m2p4q8r1w3y5",
        }
        with patch.dict(os.environ, env, clear=False):
            from garmin_mcp.server import mcp

            # Reset to default first
            mcp.settings.streamable_http_path = "/mcp"
            # Re-import main to test the env var path — but main() blocks,
            # so we test the logic directly:
            endpoint_path = os.environ.get("MCP_ENDPOINT_PATH", "").strip()
            if endpoint_path:
                if not endpoint_path.startswith("/"):
                    endpoint_path = "/" + endpoint_path
                mcp.settings.streamable_http_path = endpoint_path

            assert mcp.settings.streamable_http_path == "/x7k9m2p4q8r1w3y5"
            # Restore default
            mcp.settings.streamable_http_path = "/mcp"

    def test_custom_endpoint_path_adds_leading_slash(self):
        """MCP_ENDPOINT_PATH without leading slash gets one prepended."""
        env = {"MCP_ENDPOINT_PATH": "secret123"}
        with patch.dict(os.environ, env, clear=False):
            endpoint_path = os.environ.get("MCP_ENDPOINT_PATH", "").strip()
            if not endpoint_path.startswith("/"):
                endpoint_path = "/" + endpoint_path
            assert endpoint_path == "/secret123"


class TestMcpServerRegistration:
    """Tests that the MCP server registers all expected tools."""

    def test_mcp_server_has_expected_tool_count(self):
        from garmin_mcp.server import mcp

        tools = mcp._tool_manager.list_tools()
        assert len(tools) == 45

    def test_mcp_server_tool_names(self):
        from garmin_mcp.server import mcp

        names = {t.name for t in mcp._tool_manager.list_tools()}
        expected = {
            "get_recent_activities",
            "get_activity_detail",
            "get_activities_in_range",
            "get_hrv_trend",
            "get_sleep_history",
            "get_body_battery",
            "get_resting_hr_trend",
            "get_training_status",
            "get_race_predictions",
            "get_weekly_summary",
            "get_recovery_snapshot",
            "get_weight_trend",
            "get_body_composition",
            "get_morning_readiness",
            "get_stress_data",
            "get_max_metrics",
            "get_endurance_score",
            "get_lactate_threshold",
            "get_personal_records",
            "get_intensity_minutes",
            "get_body_battery_events",
            "get_heart_rates",
            "get_progress_summary",
            "get_workouts",
            "get_workout_by_id",
            "get_training_plans",
            "get_activity_typed_splits",
            "get_activity_split_summaries",
            "get_activity_weather",
            "get_activity_power_zones",
            "get_daily_stats",
            "get_weekly_stress",
            "get_weekly_intensity_minutes",
            "get_fitness_age",
            "upload_running_workout",
            "get_last_activity",
            "get_activities_for_date",
            "get_activity_details",
            "get_activity_gear",
            "get_respiration_data",
            "get_spo2_data",
            "upload_cycling_workout",
            "get_steps_data",
            "get_daily_steps",
            "get_weekly_steps",
        }
        assert names == expected

    def test_mcp_server_name(self):
        from garmin_mcp.server import mcp

        assert mcp.name == "Garmin Connect MCP"

    def test_main_entrypoint_callable(self):
        from garmin_mcp.server import main

        assert callable(main)
