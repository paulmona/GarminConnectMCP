"""Smoke tests verifying both the web server and MCP server can actually start."""

import socket
import threading
import time

import httpx
import pytest
import uvicorn

from garmin_mcp.web.app import app


def _free_port() -> int:
    """Return a free TCP port on localhost."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestWebServerStartup:
    """Tests that the FastAPI web server binds and responds to real HTTP requests."""

    def test_server_starts_and_responds(self):
        port = _free_port()
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        try:
            for _ in range(40):
                try:
                    r = httpx.get(
                        f"http://127.0.0.1:{port}/setup", follow_redirects=False
                    )
                    assert r.status_code == 200
                    return
                except httpx.ConnectError:
                    time.sleep(0.1)
            pytest.fail("Web server did not start within 4 seconds")
        finally:
            server.should_exit = True
            thread.join(timeout=5)

    def test_setup_page_returns_html(self):
        port = _free_port()
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        try:
            for _ in range(40):
                try:
                    r = httpx.get(
                        f"http://127.0.0.1:{port}/setup", follow_redirects=False
                    )
                    assert "text/html" in r.headers["content-type"]
                    assert "GarminClaudeSync" in r.text
                    return
                except httpx.ConnectError:
                    time.sleep(0.1)
            pytest.fail("Web server did not start within 4 seconds")
        finally:
            server.should_exit = True
            thread.join(timeout=5)

    def test_static_css_served(self):
        port = _free_port()
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        try:
            for _ in range(40):
                try:
                    r = httpx.get(
                        f"http://127.0.0.1:{port}/static/style.css",
                        follow_redirects=False,
                    )
                    assert r.status_code == 200
                    assert "text/css" in r.headers["content-type"]
                    return
                except httpx.ConnectError:
                    time.sleep(0.1)
            pytest.fail("Web server did not start within 4 seconds")
        finally:
            server.should_exit = True
            thread.join(timeout=5)


class TestMcpServerRegistration:
    """Tests that the MCP server registers all expected tools."""

    def test_mcp_server_has_eleven_tools(self):
        from garmin_mcp.server import mcp

        tools = mcp._tool_manager.list_tools()
        assert len(tools) == 11

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
        }
        assert names == expected

    def test_mcp_server_name(self):
        from garmin_mcp.server import mcp

        assert mcp.name == "garmin-mcp"

    def test_main_entrypoint_callable(self):
        from garmin_mcp.server import main

        assert callable(main)

    def test_web_start_entrypoint_callable(self):
        from garmin_mcp.web.app import start

        assert callable(start)
