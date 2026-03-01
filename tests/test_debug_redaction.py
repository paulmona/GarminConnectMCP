"""Tests for MCP_DEBUG-gated log redaction in ASGI middleware."""

import json
import logging

import pytest


async def _simple_app(scope, receive, send):
    """Minimal ASGI app that always returns 200 OK."""
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({"type": "http.response.body", "body": b"OK", "more_body": False})


async def _token_app(scope, receive, send):
    """ASGI app that reads the request body and returns a JSON token response."""
    # Must call receive() so _TokenEndpointMiddleware's logging_receive fires
    await receive()
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"application/json")],
    })
    body = json.dumps({
        "access_token": "super-secret-token-value",
        "token_type": "Bearer",
        "scope": "claudeai",
    }).encode()
    await send({"type": "http.response.body", "body": body, "more_body": False})


def _make_http_scope(path="/test", method="GET", headers=None):
    return {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": headers or [],
    }


class TestRequestLogRedaction:
    """_RequestLogMiddleware should redact Bearer tokens unless MCP_DEBUG=true."""

    async def test_auth_redacted_by_default(self, monkeypatch, caplog):
        monkeypatch.setattr("garmin_mcp.server._DEBUG", False)
        from garmin_mcp.server import _RequestLogMiddleware

        mw = _RequestLogMiddleware(_simple_app)
        scope = _make_http_scope(headers=[
            (b"authorization", b"Bearer my-secret-token-12345"),
        ])
        responses = []

        async def receive():
            return {}

        async def send(event):
            responses.append(event)

        with caplog.at_level(logging.INFO, logger="garmin_mcp.server"):
            await mw(scope, receive, send)

        req_logs = [r for r in caplog.records if "REQ" in r.message]
        assert len(req_logs) >= 1
        assert "my-secret" not in req_logs[0].message
        assert "Bearer ***" in req_logs[0].message

    async def test_auth_visible_in_debug_mode(self, monkeypatch, caplog):
        monkeypatch.setattr("garmin_mcp.server._DEBUG", True)
        from garmin_mcp.server import _RequestLogMiddleware

        mw = _RequestLogMiddleware(_simple_app)
        scope = _make_http_scope(headers=[
            (b"authorization", b"Bearer my-secret-token-12345"),
        ])
        responses = []

        async def receive():
            return {}

        async def send(event):
            responses.append(event)

        with caplog.at_level(logging.INFO, logger="garmin_mcp.server"):
            await mw(scope, receive, send)

        req_logs = [r for r in caplog.records if "REQ" in r.message]
        assert len(req_logs) >= 1
        assert "my-secret" in req_logs[0].message


class TestTokenEndpointRedaction:
    """_TokenEndpointMiddleware should redact request/response bodies unless MCP_DEBUG."""

    async def test_token_request_redacted_by_default(self, monkeypatch, caplog):
        monkeypatch.setattr("garmin_mcp.server._DEBUG", False)
        from garmin_mcp.server import _TokenEndpointMiddleware

        mw = _TokenEndpointMiddleware(_token_app, resource_url="https://example.com/mcp")
        scope = _make_http_scope(path="/token", method="POST")
        req_body = b"grant_type=authorization_code&code=secret-auth-code"

        async def receive():
            return {"type": "http.request", "body": req_body, "more_body": False}

        responses = []

        async def send(event):
            responses.append(event)

        with caplog.at_level(logging.INFO, logger="garmin_mcp.server"):
            await mw(scope, receive, send)

        req_logs = [r for r in caplog.records if "TOKEN REQUEST body:" in r.message]
        assert len(req_logs) == 1
        assert "secret-auth-code" not in req_logs[0].message
        assert "bytes" in req_logs[0].message

    async def test_token_request_visible_in_debug(self, monkeypatch, caplog):
        monkeypatch.setattr("garmin_mcp.server._DEBUG", True)
        from garmin_mcp.server import _TokenEndpointMiddleware

        mw = _TokenEndpointMiddleware(_token_app, resource_url="https://example.com/mcp")
        scope = _make_http_scope(path="/token", method="POST")
        req_body = b"grant_type=authorization_code&code=secret-auth-code"

        async def receive():
            return {"type": "http.request", "body": req_body, "more_body": False}

        responses = []

        async def send(event):
            responses.append(event)

        with caplog.at_level(logging.INFO, logger="garmin_mcp.server"):
            await mw(scope, receive, send)

        req_logs = [r for r in caplog.records if "TOKEN REQUEST body:" in r.message]
        assert len(req_logs) == 1
        assert "secret-auth-code" in req_logs[0].message

    async def test_token_response_redacted_by_default(self, monkeypatch, caplog):
        monkeypatch.setattr("garmin_mcp.server._DEBUG", False)
        from garmin_mcp.server import _TokenEndpointMiddleware

        mw = _TokenEndpointMiddleware(_token_app, resource_url="https://example.com/mcp")
        scope = _make_http_scope(path="/token", method="POST")

        async def receive():
            return {"type": "http.request", "body": b"grant_type=authorization_code", "more_body": False}

        responses = []

        async def send(event):
            responses.append(event)

        with caplog.at_level(logging.INFO, logger="garmin_mcp.server"):
            await mw(scope, receive, send)

        rsp_logs = [r for r in caplog.records if "TOKEN RESPONSE:" in r.message]
        assert len(rsp_logs) == 1
        assert "super-secret-token-value" not in rsp_logs[0].message
        assert "token_type=Bearer" in rsp_logs[0].message

    async def test_token_response_visible_in_debug(self, monkeypatch, caplog):
        monkeypatch.setattr("garmin_mcp.server._DEBUG", True)
        from garmin_mcp.server import _TokenEndpointMiddleware

        mw = _TokenEndpointMiddleware(_token_app, resource_url="https://example.com/mcp")
        scope = _make_http_scope(path="/token", method="POST")

        async def receive():
            return {"type": "http.request", "body": b"grant_type=authorization_code", "more_body": False}

        responses = []

        async def send(event):
            responses.append(event)

        with caplog.at_level(logging.INFO, logger="garmin_mcp.server"):
            await mw(scope, receive, send)

        rsp_logs = [r for r in caplog.records if "TOKEN RESPONSE:" in r.message]
        assert len(rsp_logs) == 1
        assert "super-secret-token-value" in rsp_logs[0].message
