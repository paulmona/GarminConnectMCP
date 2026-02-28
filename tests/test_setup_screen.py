"""Tests for the web UI setup screen and setup_guard middleware."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from garmin_mcp.web.app import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestSetupGuardMiddleware:
    """Tests for the setup_guard middleware redirect."""

    @patch("garmin_mcp.web.app.credentials.exists", return_value=False)
    async def test_redirects_to_setup_when_no_credentials(self, _mock_exists, client):
        response = await client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/setup"

    @patch("garmin_mcp.web.app.credentials.exists", return_value=False)
    async def test_setup_page_not_redirected(self, _mock_exists, client):
        response = await client.get("/setup", follow_redirects=False)
        assert response.status_code == 200

    @patch("garmin_mcp.web.app.credentials.exists", return_value=False)
    async def test_static_not_redirected(self, _mock_exists, client):
        response = await client.get("/static/style.css", follow_redirects=False)
        # Should not be 302 redirect (may be 200 or 404 depending on file)
        assert response.status_code != 302

    @patch("garmin_mcp.web.app.credentials.exists", return_value=True)
    @patch("garmin_mcp.web.app.credentials.load")
    async def test_no_redirect_when_credentials_exist(self, mock_load, _mock_exists, client):
        mock_load.return_value = {"email": "a@b.com", "password": "pw"}
        response = await client.get("/", follow_redirects=False)
        assert response.status_code == 200


class TestSetupPage:
    """Tests for the /setup GET and POST endpoints."""

    @patch("garmin_mcp.web.app.credentials.exists", return_value=False)
    async def test_setup_page_renders(self, _mock_exists, client):
        response = await client.get("/setup")
        assert response.status_code == 200
        assert "Welcome to GarminClaudeSync" in response.text
        assert "csrf_token" in response.text

    @patch("garmin_mcp.web.app.credentials.exists", return_value=False)
    async def test_setup_post_requires_email_and_password(self, _mock_exists, client):
        # First GET to establish session and get CSRF token
        get_resp = await client.get("/setup")
        session_cookie = get_resp.cookies.get("gcs_session")

        # Extract CSRF token from response
        import re
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_resp.text)
        assert match, "CSRF token not found in setup page"
        csrf_token = match.group(1)

        # POST without email/password
        response = await client.post(
            "/setup",
            data={"csrf_token": csrf_token, "email": "", "password": ""},
            cookies={"gcs_session": session_cookie},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "required" in response.text.lower()
