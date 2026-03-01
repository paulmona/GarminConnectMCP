"""Tests for the TOTP gate ASGI middleware."""

from urllib.parse import urlencode

import pyotp
import pytest

from garmin_mcp.server import _TOTPGateMiddleware

_TEST_SECRET = "JBSWY3DPEHPK3PXP"


async def _simple_app(scope, receive, send):
    """Minimal ASGI app that always returns 200 OK."""
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({"type": "http.response.body", "body": b"OK", "more_body": False})


def _make_scope(path="/authorize", method="GET", query_string=b""):
    return {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query_string,
        "headers": [],
    }


async def _collect_response(middleware, scope, body=b""):
    """Drive the middleware and collect status, headers, and body."""
    responses: list[dict] = []
    body_chunks: list[bytes] = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(event):
        responses.append(event)
        if event["type"] == "http.response.body":
            body_chunks.append(event.get("body", b""))

    await middleware(scope, receive, send)
    start = next((r for r in responses if r["type"] == "http.response.start"), None)
    status = start["status"] if start else None
    headers = start.get("headers", []) if start else []
    return status, headers, b"".join(body_chunks)


class TestTOTPGateMiddleware:
    async def test_get_authorize_returns_html_form(self):
        mw = _TOTPGateMiddleware(_simple_app, _TEST_SECRET)
        scope = _make_scope(
            query_string=b"response_type=code&client_id=abc&state=xyz"
        )
        status, headers, body = await _collect_response(mw, scope)
        assert status == 200
        assert b"text/html" in dict(headers).get(b"content-type", b"")
        assert b'name="totp_code"' in body
        assert b'name="response_type"' in body
        assert b'value="code"' in body
        assert b'name="client_id"' in body
        assert b'value="abc"' in body
        assert b'name="state"' in body
        assert b'value="xyz"' in body

    async def test_post_valid_totp_passes_through(self):
        valid_code = pyotp.TOTP(_TEST_SECRET).now()

        reached_inner: list[dict] = []

        async def tracking_app(scope, receive, send):
            reached_inner.append(scope)
            await _simple_app(scope, receive, send)

        mw = _TOTPGateMiddleware(tracking_app, _TEST_SECRET)
        form_body = urlencode({
            "response_type": "code",
            "client_id": "abc",
            "state": "xyz",
            "totp_code": valid_code,
        }).encode()
        scope = _make_scope(method="POST")
        status, _, _ = await _collect_response(mw, scope, body=form_body)
        assert status == 200
        assert len(reached_inner) == 1
        inner_scope = reached_inner[0]
        assert inner_scope["method"] == "GET"
        qs = inner_scope["query_string"].decode()
        assert "response_type=code" in qs
        assert "client_id=abc" in qs
        assert "totp_code" not in qs

    async def test_post_invalid_totp_shows_error(self):
        mw = _TOTPGateMiddleware(_simple_app, _TEST_SECRET)
        form_body = urlencode({
            "response_type": "code",
            "client_id": "abc",
            "totp_code": "000000",
        }).encode()
        scope = _make_scope(method="POST")
        status, _, body = await _collect_response(mw, scope, body=form_body)
        assert status == 200
        assert b"Invalid code" in body
        # OAuth params preserved for retry
        assert b'value="code"' in body
        assert b'value="abc"' in body

    async def test_non_authorize_path_passes_through(self):
        reached: list[bool] = []

        async def marker_app(scope, receive, send):
            reached.append(True)
            await _simple_app(scope, receive, send)

        mw = _TOTPGateMiddleware(marker_app, _TEST_SECRET)
        scope = _make_scope(path="/token", method="POST")
        await _collect_response(mw, scope)
        assert reached == [True]

    async def test_non_http_scope_passes_through(self):
        reached: list[bool] = []

        async def marker_app(scope, receive, send):
            reached.append(True)

        mw = _TOTPGateMiddleware(marker_app, _TEST_SECRET)
        await mw({"type": "lifespan"}, None, None)
        assert reached == [True]

    async def test_html_escaping_prevents_xss(self):
        mw = _TOTPGateMiddleware(_simple_app, _TEST_SECRET)
        scope = _make_scope(
            query_string=b"client_id=%3Cscript%3Ealert(1)%3C%2Fscript%3E"
        )
        _, _, body = await _collect_response(mw, scope)
        assert b"<script>" not in body
        assert b"&lt;script&gt;" in body

    async def test_totp_code_stripped_from_forwarded_query(self):
        valid_code = pyotp.TOTP(_TEST_SECRET).now()
        forwarded_scopes: list[dict] = []

        async def capture_app(scope, receive, send):
            forwarded_scopes.append(scope)
            await _simple_app(scope, receive, send)

        mw = _TOTPGateMiddleware(capture_app, _TEST_SECRET)
        form_body = urlencode({
            "client_id": "test",
            "totp_code": valid_code,
        }).encode()
        scope = _make_scope(method="POST")
        await _collect_response(mw, scope, body=form_body)
        qs = forwarded_scopes[0]["query_string"].decode()
        assert "client_id=test" in qs
        assert "totp_code" not in qs
