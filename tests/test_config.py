"""Tests for garmin_mcp.config.Settings."""

from pathlib import Path
from unittest.mock import patch

import pytest

from garmin_mcp.config import Settings
from garmin_mcp.credentials import CredentialsNotConfiguredError


class TestSettingsLoad:
    """Tests for Settings.load()."""

    @patch("garmin_mcp.config.credentials.load")
    def test_loads_credentials_from_file(self, mock_creds_load):
        mock_creds_load.return_value = {
            "email": "user@example.com",
            "password": "secret",
        }
        settings = Settings.load()
        assert settings.garmin_email == "user@example.com"
        assert settings.garmin_password == "secret"

    @patch("garmin_mcp.config.credentials.load")
    def test_default_session_dir(self, mock_creds_load):
        mock_creds_load.return_value = {
            "email": "user@example.com",
            "password": "secret",
        }
        settings = Settings.load()
        assert settings.session_dir == Path("config/.session").resolve()

    @patch.dict(
        "os.environ",
        {"GARMIN_SESSION_DIR": "/tmp/garmin_sessions"},
        clear=False,
    )
    @patch("garmin_mcp.config.credentials.load")
    def test_custom_session_dir(self, mock_creds_load):
        mock_creds_load.return_value = {
            "email": "user@example.com",
            "password": "secret",
        }
        settings = Settings.load()
        assert settings.session_dir == Path("/tmp/garmin_sessions").resolve()

    @patch("garmin_mcp.config.credentials.load", return_value=None)
    def test_raises_when_credentials_missing(self, _mock_creds_load):
        with pytest.raises(
            CredentialsNotConfiguredError,
            match="Garmin credentials not configured",
        ):
            Settings.load()

    def test_settings_is_frozen(self):
        settings = Settings(
            garmin_email="a@b.com",
            garmin_password="pw",
            session_dir=Path("/tmp"),
        )
        with pytest.raises(AttributeError):
            settings.garmin_email = "other@b.com"
