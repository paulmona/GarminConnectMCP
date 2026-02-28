"""Tests for MCP server graceful degradation when credentials are not configured."""

import json
from unittest.mock import patch

from garmin_mcp.credentials import CredentialsNotConfiguredError
from garmin_mcp.server import NOT_CONFIGURED_MSG


def _raise_not_configured(*args, **kwargs):
    raise CredentialsNotConfiguredError("not configured")


class TestMcpToolsUnconfigured:
    """Verify MCP tools return NOT_CONFIGURED_MSG when credentials are missing."""

    @patch("garmin_mcp.server._get_client")
    def test_get_recent_activities_returns_not_configured(self, mock_get_client):
        mock_client = mock_get_client.return_value
        mock_client.call_with_retry.side_effect = CredentialsNotConfiguredError("not configured")

        from garmin_mcp.server import get_recent_activities
        result = get_recent_activities()

        parsed = json.loads(result)
        assert parsed["error"] == "not_configured"
        assert "localhost:8585/setup" in parsed["message"]

    @patch("garmin_mcp.server._get_client")
    def test_get_training_status_returns_not_configured(self, mock_get_client):
        mock_client = mock_get_client.return_value
        mock_client.call_with_retry.side_effect = CredentialsNotConfiguredError("not configured")

        from garmin_mcp.server import get_training_status
        result = get_training_status()

        parsed = json.loads(result)
        assert parsed["error"] == "not_configured"
        assert "localhost:8585/setup" in parsed["message"]

    @patch("garmin_mcp.server._get_client")
    def test_get_recovery_snapshot_returns_not_configured(self, mock_get_client):
        mock_client = mock_get_client.return_value
        mock_client.call_with_retry.side_effect = CredentialsNotConfiguredError("not configured")

        from garmin_mcp.server import get_recovery_snapshot
        result = get_recovery_snapshot()

        parsed = json.loads(result)
        assert parsed["error"] == "not_configured"

    def test_not_configured_msg_is_valid_json(self):
        parsed = json.loads(NOT_CONFIGURED_MSG)
        assert "error" in parsed
        assert "message" in parsed
        assert parsed["error"] == "not_configured"
