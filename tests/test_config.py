"""Tests for garmin_mcp.config.Settings."""

from pathlib import Path
from unittest.mock import patch

import pytest

from garmin_mcp.config import Settings


class TestSettingsFromEnv:
    """Tests for Settings.from_env()."""

    @patch.dict(
        "os.environ",
        {"GARMIN_EMAIL": "user@example.com", "GARMIN_PASSWORD": "secret"},
        clear=True,
    )
    @patch("garmin_mcp.config.load_dotenv")
    def test_loads_credentials_from_env(self, _mock_dotenv):
        settings = Settings.from_env()
        assert settings.garmin_email == "user@example.com"
        assert settings.garmin_password == "secret"

    @patch.dict(
        "os.environ",
        {"GARMIN_EMAIL": "user@example.com", "GARMIN_PASSWORD": "secret"},
        clear=True,
    )
    @patch("garmin_mcp.config.load_dotenv")
    def test_default_session_dir(self, _mock_dotenv):
        settings = Settings.from_env()
        assert settings.session_dir == Path(".session").resolve()

    @patch.dict(
        "os.environ",
        {
            "GARMIN_EMAIL": "user@example.com",
            "GARMIN_PASSWORD": "secret",
            "GARMIN_SESSION_DIR": "/tmp/garmin_sessions",
        },
        clear=True,
    )
    @patch("garmin_mcp.config.load_dotenv")
    def test_custom_session_dir(self, _mock_dotenv):
        settings = Settings.from_env()
        assert settings.session_dir == Path("/tmp/garmin_sessions").resolve()

    @patch.dict("os.environ", {}, clear=True)
    @patch("garmin_mcp.config.load_dotenv")
    def test_raises_when_credentials_missing(self, _mock_dotenv):
        with pytest.raises(ValueError, match="GARMIN_EMAIL and GARMIN_PASSWORD"):
            Settings.from_env()

    @patch.dict("os.environ", {"GARMIN_EMAIL": "user@example.com"}, clear=True)
    @patch("garmin_mcp.config.load_dotenv")
    def test_raises_when_password_missing(self, _mock_dotenv):
        with pytest.raises(ValueError, match="GARMIN_EMAIL and GARMIN_PASSWORD"):
            Settings.from_env()

    @patch.dict("os.environ", {"GARMIN_PASSWORD": "secret"}, clear=True)
    @patch("garmin_mcp.config.load_dotenv")
    def test_raises_when_email_missing(self, _mock_dotenv):
        with pytest.raises(ValueError, match="GARMIN_EMAIL and GARMIN_PASSWORD"):
            Settings.from_env()

    @patch.dict(
        "os.environ",
        {"GARMIN_EMAIL": "user@example.com", "GARMIN_PASSWORD": "secret"},
        clear=True,
    )
    @patch("garmin_mcp.config.load_dotenv")
    def test_calls_load_dotenv(self, mock_dotenv):
        Settings.from_env()
        mock_dotenv.assert_called_once()

    def test_settings_is_frozen(self):
        settings = Settings(
            garmin_email="a@b.com",
            garmin_password="pw",
            session_dir=Path("/tmp"),
        )
        with pytest.raises(AttributeError):
            settings.garmin_email = "other@b.com"
