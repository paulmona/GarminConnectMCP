"""Smoke tests verifying the MCP server registers all expected tools."""


class TestMcpServerRegistration:
    """Tests that the MCP server registers all expected tools."""

    def test_mcp_server_has_expected_tool_count(self):
        from garmin_mcp.server import mcp

        tools = mcp._tool_manager.list_tools()
        assert len(tools) == 26

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
        }
        assert names == expected

    def test_mcp_server_name(self):
        from garmin_mcp.server import mcp

        assert mcp.name == "Garmin Connect MCP"

    def test_main_entrypoint_callable(self):
        from garmin_mcp.server import main

        assert callable(main)
