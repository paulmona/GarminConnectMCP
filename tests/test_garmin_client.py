"""Tests for garmin_mcp.garmin_client.GarminClient."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from garminconnect import GarminConnectAuthenticationError

from garmin_mcp.config import Settings
from garmin_mcp.garmin_client import GarminClient


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        garmin_email="user@example.com",
        garmin_password="secret",
        session_dir=tmp_path / "sessions",
    )


class TestGarminClientInit:
    """Test GarminClient construction."""

    def test_accepts_explicit_settings(self, tmp_path):
        settings = _make_settings(tmp_path)
        client = GarminClient(settings=settings)
        assert client._settings is settings

    @patch("garmin_mcp.garmin_client.Settings.from_env")
    def test_defaults_to_settings_from_env(self, mock_from_env):
        mock_from_env.return_value = Settings(
            garmin_email="e", garmin_password="p", session_dir=Path("/tmp")
        )
        client = GarminClient()
        mock_from_env.assert_called_once()
        assert client._settings is mock_from_env.return_value


class TestApiProperty:
    """Test the lazy-authenticated api property."""

    @patch("garmin_mcp.garmin_client.Garmin")
    def test_api_returns_authenticated_client(self, MockGarmin, tmp_path):
        settings = _make_settings(tmp_path)
        mock_instance = MockGarmin.return_value
        mock_instance.garth = MagicMock()

        gc = GarminClient(settings=settings)
        api = gc.api

        assert api is mock_instance
        mock_instance.login.assert_called_once()

    @patch("garmin_mcp.garmin_client.Garmin")
    def test_api_caches_client_across_calls(self, MockGarmin, tmp_path):
        settings = _make_settings(tmp_path)
        mock_instance = MockGarmin.return_value
        mock_instance.garth = MagicMock()

        gc = GarminClient(settings=settings)
        first = gc.api
        second = gc.api

        assert first is second
        # Garmin() constructor called only once
        assert MockGarmin.call_count == 1


class TestAuthenticate:
    """Test _authenticate login flow."""

    @patch("garmin_mcp.garmin_client.Garmin")
    def test_token_login_succeeds(self, MockGarmin, tmp_path):
        settings = _make_settings(tmp_path)
        mock_instance = MockGarmin.return_value
        mock_instance.garth = MagicMock()

        gc = GarminClient(settings=settings)
        result = gc._authenticate()

        assert result is mock_instance
        # First call uses tokenstore
        token_path = str(settings.session_dir / "tokens")
        mock_instance.login.assert_called_once_with(tokenstore=token_path)
        # Tokens saved
        mock_instance.garth.dump.assert_called_once_with(token_path)

    @patch("garmin_mcp.garmin_client.Garmin")
    def test_falls_back_to_fresh_login(self, MockGarmin, tmp_path):
        settings = _make_settings(tmp_path)
        mock_instance = MockGarmin.return_value
        mock_instance.garth = MagicMock()

        # First login (with tokenstore) fails; second (fresh) succeeds
        mock_instance.login.side_effect = [
            GarminConnectAuthenticationError("bad token"),
            None,
        ]

        gc = GarminClient(settings=settings)
        result = gc._authenticate()

        assert result is mock_instance
        assert mock_instance.login.call_count == 2
        # Second call is without tokenstore
        mock_instance.login.assert_called_with()

    @patch("garmin_mcp.garmin_client.Garmin")
    def test_raises_when_both_attempts_fail(self, MockGarmin, tmp_path):
        settings = _make_settings(tmp_path)
        mock_instance = MockGarmin.return_value

        mock_instance.login.side_effect = GarminConnectAuthenticationError(
            "invalid"
        )

        gc = GarminClient(settings=settings)
        with pytest.raises(GarminConnectAuthenticationError, match="after retry"):
            gc._authenticate()

    @patch("garmin_mcp.garmin_client.Garmin")
    def test_creates_session_dir(self, MockGarmin, tmp_path):
        session_dir = tmp_path / "deep" / "nested" / "sessions"
        settings = Settings(
            garmin_email="u@e.com",
            garmin_password="pw",
            session_dir=session_dir,
        )
        mock_instance = MockGarmin.return_value
        mock_instance.garth = MagicMock()

        gc = GarminClient(settings=settings)
        gc._authenticate()

        assert session_dir.exists()

    @patch("garmin_mcp.garmin_client.Garmin")
    def test_passes_credentials_to_garmin(self, MockGarmin, tmp_path):
        settings = _make_settings(tmp_path)
        mock_instance = MockGarmin.return_value
        mock_instance.garth = MagicMock()

        gc = GarminClient(settings=settings)
        gc._authenticate()

        MockGarmin.assert_called_once_with(
            email="user@example.com",
            password="secret",
        )


class TestSaveTokens:
    """Test _save_tokens static method."""

    def test_saves_tokens_to_path(self):
        mock_client = MagicMock()
        GarminClient._save_tokens(mock_client, "/tmp/tokens")
        mock_client.garth.dump.assert_called_once_with("/tmp/tokens")

    def test_swallows_exceptions_on_save_failure(self):
        mock_client = MagicMock()
        mock_client.garth.dump.side_effect = OSError("disk full")
        # Should not raise
        GarminClient._save_tokens(mock_client, "/tmp/tokens")
