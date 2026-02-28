"""Tests for garmin_mcp.credentials module."""

import json
import os
import stat
from pathlib import Path

import pytest

from garmin_mcp import credentials


class TestLoad:
    """Tests for credentials.load()."""

    def test_returns_none_when_file_missing(self, tmp_path):
        result = credentials.load(tmp_path / "nonexistent.json")
        assert result is None

    def test_returns_dict_when_file_exists(self, tmp_path):
        path = tmp_path / "auth.json"
        path.write_text(json.dumps({"email": "a@b.com", "password": "pw"}))
        result = credentials.load(path)
        assert result == {"email": "a@b.com", "password": "pw"}

    def test_returns_none_when_email_empty(self, tmp_path):
        path = tmp_path / "auth.json"
        path.write_text(json.dumps({"email": "", "password": "pw"}))
        assert credentials.load(path) is None

    def test_returns_none_when_password_empty(self, tmp_path):
        path = tmp_path / "auth.json"
        path.write_text(json.dumps({"email": "a@b.com", "password": ""}))
        assert credentials.load(path) is None

    def test_returns_none_when_fields_missing(self, tmp_path):
        path = tmp_path / "auth.json"
        path.write_text(json.dumps({}))
        assert credentials.load(path) is None

    def test_returns_none_on_invalid_json(self, tmp_path):
        path = tmp_path / "auth.json"
        path.write_text("not json")
        assert credentials.load(path) is None

    def test_strips_whitespace(self, tmp_path):
        path = tmp_path / "auth.json"
        path.write_text(json.dumps({"email": "  a@b.com  ", "password": "  pw  "}))
        result = credentials.load(path)
        assert result == {"email": "a@b.com", "password": "pw"}

    def test_returns_none_when_whitespace_only(self, tmp_path):
        path = tmp_path / "auth.json"
        path.write_text(json.dumps({"email": "   ", "password": "   "}))
        assert credentials.load(path) is None


class TestSave:
    """Tests for credentials.save()."""

    def test_writes_file_with_correct_content(self, tmp_path):
        path = tmp_path / "auth.json"
        credentials.save("a@b.com", "pw", path)
        data = json.loads(path.read_text())
        assert data == {"email": "a@b.com", "password": "pw"}

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "auth.json"
        credentials.save("a@b.com", "pw", path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["email"] == "a@b.com"

    def test_sets_0600_permissions(self, tmp_path):
        path = tmp_path / "auth.json"
        credentials.save("a@b.com", "pw", path)
        mode = os.stat(path).st_mode & 0o777
        assert mode == stat.S_IRUSR | stat.S_IWUSR  # 0o600

    def test_overwrites_existing_file(self, tmp_path):
        path = tmp_path / "auth.json"
        credentials.save("old@b.com", "old", path)
        credentials.save("new@b.com", "new", path)
        data = json.loads(path.read_text())
        assert data == {"email": "new@b.com", "password": "new"}


class TestExists:
    """Tests for credentials.exists()."""

    def test_false_when_file_missing(self, tmp_path):
        assert credentials.exists(tmp_path / "nonexistent.json") is False

    def test_true_when_valid_credentials(self, tmp_path):
        path = tmp_path / "auth.json"
        credentials.save("a@b.com", "pw", path)
        assert credentials.exists(path) is True

    def test_false_when_incomplete(self, tmp_path):
        path = tmp_path / "auth.json"
        path.write_text(json.dumps({"email": "", "password": ""}))
        assert credentials.exists(path) is False
