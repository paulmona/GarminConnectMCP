"""Tests for garmin_mcp.config.Settings."""

from pathlib import Path

import pytest

from garmin_mcp.config import CredentialsNotConfiguredError, Settings


class TestSettingsLoad:
    """Tests for Settings.load()."""

    def test_loads_credentials_from_env(self, monkeypatch):
        monkeypatch.setenv("GARMIN_EMAIL", "user@example.com")
        monkeypatch.setenv("GARMIN_PASSWORD", "secret")
        settings = Settings.load()
        assert settings.garmin_email == "user@example.com"
        assert settings.garmin_password == "secret"

    def test_default_session_dir(self, monkeypatch):
        monkeypatch.setenv("GARMIN_EMAIL", "user@example.com")
        monkeypatch.setenv("GARMIN_PASSWORD", "secret")
        monkeypatch.delenv("GARMIN_SESSION_DIR", raising=False)
        settings = Settings.load()
        assert settings.session_dir == Path("config/.session").resolve()

    def test_custom_session_dir(self, monkeypatch):
        monkeypatch.setenv("GARMIN_EMAIL", "user@example.com")
        monkeypatch.setenv("GARMIN_PASSWORD", "secret")
        monkeypatch.setenv("GARMIN_SESSION_DIR", "/tmp/garmin_sessions")
        settings = Settings.load()
        assert settings.session_dir == Path("/tmp/garmin_sessions").resolve()

    def test_raises_when_email_missing(self, monkeypatch):
        monkeypatch.delenv("GARMIN_EMAIL", raising=False)
        monkeypatch.setenv("GARMIN_PASSWORD", "secret")
        with pytest.raises(CredentialsNotConfiguredError):
            Settings.load()

    def test_raises_when_password_missing(self, monkeypatch):
        monkeypatch.setenv("GARMIN_EMAIL", "user@example.com")
        monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
        with pytest.raises(CredentialsNotConfiguredError):
            Settings.load()

    def test_raises_when_both_missing(self, monkeypatch):
        monkeypatch.delenv("GARMIN_EMAIL", raising=False)
        monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
        with pytest.raises(CredentialsNotConfiguredError):
            Settings.load()

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("GARMIN_EMAIL", "  user@example.com  ")
        monkeypatch.setenv("GARMIN_PASSWORD", "  secret  ")
        settings = Settings.load()
        assert settings.garmin_email == "user@example.com"
        assert settings.garmin_password == "secret"

    def test_settings_is_frozen(self):
        settings = Settings(
            garmin_email="a@b.com",
            garmin_password="pw",
            session_dir=Path("/tmp"),
        )
        with pytest.raises(AttributeError):
            settings.garmin_email = "other@b.com"
