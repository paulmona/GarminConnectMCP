"""Tests for OAuth state persistence across provider restarts."""

import json
import os
import tempfile

import pytest


@pytest.fixture
def persist_file(tmp_path):
    """Return a path to a temporary persistence file."""
    return str(tmp_path / "oauth_state.json")


def _make_provider(api_key="test-key", persist_path=None):
    from garmin_mcp.server import _SimpleOAuthProvider

    return _SimpleOAuthProvider(api_key, persist_path=persist_path)


class TestOAuthPersistence:
    async def test_save_and_restore_clients(self, persist_file):
        """Registered clients survive a provider restart."""
        from mcp.server.auth.provider import OAuthClientInformationFull

        provider = _make_provider(persist_path=persist_file)
        client_info = OAuthClientInformationFull(
            client_id="claude-web",
            client_secret="s3cret",
            redirect_uris=["https://example.com/callback"],
        )
        await provider.register_client(client_info)

        # New provider loads from same file
        provider2 = _make_provider(persist_path=persist_file)
        restored = await provider2.get_client("claude-web")
        assert restored is not None
        assert restored.client_id == "claude-web"
        assert restored.client_secret == "s3cret"

    async def test_save_and_restore_tokens(self, persist_file):
        """Access and refresh tokens survive a provider restart."""
        from mcp.server.auth.provider import (
            AuthorizationCode,
            OAuthClientInformationFull,
        )

        provider = _make_provider(persist_path=persist_file)
        client_info = OAuthClientInformationFull(
            client_id="claude-web",
            client_secret="s3cret",
            redirect_uris=["https://example.com/callback"],
        )
        await provider.register_client(client_info)

        # Simulate issuing tokens via exchange_authorization_code
        import time

        code_obj = AuthorizationCode(
            code="test-code",
            scopes=["claudeai"],
            expires_at=time.time() + 300,
            client_id="claude-web",
            code_challenge="challenge",
            redirect_uri="https://example.com/callback",
            redirect_uri_provided_explicitly=True,
            resource=None,
        )
        provider._auth_codes["test-code"] = code_obj
        token_resp = await provider.exchange_authorization_code(client_info, code_obj)

        access_token = token_resp.access_token
        refresh_token = token_resp.refresh_token

        # New provider loads from same file
        provider2 = _make_provider(persist_path=persist_file)
        loaded_access = await provider2.load_access_token(access_token)
        assert loaded_access is not None
        assert loaded_access.scopes == ["claudeai"]

        loaded_refresh = await provider2.load_refresh_token(client_info, refresh_token)
        assert loaded_refresh is not None
        assert loaded_refresh.client_id == "claude-web"

    async def test_revoke_persists(self, persist_file):
        """Revoking a token is persisted so it stays revoked after restart."""
        from mcp.server.auth.provider import (
            AuthorizationCode,
            OAuthClientInformationFull,
        )

        provider = _make_provider(persist_path=persist_file)
        client_info = OAuthClientInformationFull(
            client_id="c1",
            client_secret="s",
            redirect_uris=["https://example.com/cb"],
        )
        await provider.register_client(client_info)

        import time

        code_obj = AuthorizationCode(
            code="c",
            scopes=["claudeai"],
            expires_at=time.time() + 300,
            client_id="c1",
            code_challenge="ch",
            redirect_uri="https://example.com/cb",
            redirect_uri_provided_explicitly=True,
            resource=None,
        )
        provider._auth_codes["c"] = code_obj
        token_resp = await provider.exchange_authorization_code(client_info, code_obj)
        access_token = token_resp.access_token

        # Revoke it
        loaded = await provider.load_access_token(access_token)
        await provider.revoke_token(loaded)

        # After restart the token should still be gone
        provider2 = _make_provider(persist_path=persist_file)
        assert await provider2.load_access_token(access_token) is None

    async def test_no_persist_path_works(self):
        """Provider works fine without persistence (backward compat)."""
        provider = _make_provider(persist_path=None)
        from mcp.server.auth.provider import OAuthClientInformationFull

        client_info = OAuthClientInformationFull(
            client_id="c1",
            client_secret="s",
            redirect_uris=["https://example.com/cb"],
        )
        await provider.register_client(client_info)
        assert await provider.get_client("c1") is not None

    async def test_corrupted_file_handled_gracefully(self, persist_file):
        """Corrupted persistence file doesn't crash the provider."""
        with open(persist_file, "w") as f:
            f.write("not valid json{{{")

        # Should not raise
        provider = _make_provider(persist_path=persist_file)
        assert await provider.get_client("anything") is None

    async def test_refresh_token_exchange_persists(self, persist_file):
        """Exchanging a refresh token persists the new tokens."""
        from mcp.server.auth.provider import (
            AuthorizationCode,
            OAuthClientInformationFull,
        )

        provider = _make_provider(persist_path=persist_file)
        client_info = OAuthClientInformationFull(
            client_id="c1",
            client_secret="s",
            redirect_uris=["https://example.com/cb"],
        )
        await provider.register_client(client_info)

        import time

        code_obj = AuthorizationCode(
            code="c",
            scopes=["claudeai"],
            expires_at=time.time() + 300,
            client_id="c1",
            code_challenge="ch",
            redirect_uri="https://example.com/cb",
            redirect_uri_provided_explicitly=True,
            resource=None,
        )
        provider._auth_codes["c"] = code_obj
        token_resp = await provider.exchange_authorization_code(client_info, code_obj)
        old_refresh = token_resp.refresh_token

        # Exchange the refresh token
        rt = await provider.load_refresh_token(client_info, old_refresh)
        new_token_resp = await provider.exchange_refresh_token(client_info, rt, ["claudeai"])
        new_access = new_token_resp.access_token
        new_refresh = new_token_resp.refresh_token

        # Restart — new tokens should be valid, old ones gone
        provider2 = _make_provider(persist_path=persist_file)
        assert await provider2.load_access_token(new_access) is not None
        assert await provider2.load_refresh_token(client_info, new_refresh) is not None
        assert await provider2.load_refresh_token(client_info, old_refresh) is None
