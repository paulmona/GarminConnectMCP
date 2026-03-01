"""Tests for the Bearer token auth ASGI middleware."""


async def _simple_app(scope, receive, send):
    """Minimal ASGI app that always returns 200 OK."""
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"OK", "more_body": False})


def _make_scope(auth_header: str | None = None, scope_type: str = "http"):
    headers = []
    if auth_header is not None:
        headers.append((b"authorization", auth_header.encode()))
    return {"type": scope_type, "headers": headers}


async def _collect_response(middleware, scope):
    """Drive the middleware and collect the status code."""
    responses = []

    async def send(event):
        responses.append(event)

    async def receive():
        return {}

    await middleware(scope, receive, send)
    start = next((r for r in responses if r["type"] == "http.response.start"), None)
    return start["status"] if start else None


class TestBearerAuthMiddleware:
    def test_valid_token_passes(self):
        import asyncio

        from garmin_mcp.server import _BearerAuthMiddleware

        mw = _BearerAuthMiddleware(_simple_app, "secret123")
        scope = _make_scope("Bearer secret123")
        status = asyncio.run(_collect_response(mw, scope))
        assert status == 200

    def test_wrong_token_returns_401(self):
        import asyncio

        from garmin_mcp.server import _BearerAuthMiddleware

        mw = _BearerAuthMiddleware(_simple_app, "secret123")
        scope = _make_scope("Bearer wrongtoken")
        status = asyncio.run(_collect_response(mw, scope))
        assert status == 401

    def test_missing_auth_header_returns_401(self):
        import asyncio

        from garmin_mcp.server import _BearerAuthMiddleware

        mw = _BearerAuthMiddleware(_simple_app, "secret123")
        scope = _make_scope(auth_header=None)
        status = asyncio.run(_collect_response(mw, scope))
        assert status == 401

    def test_basic_auth_scheme_rejected(self):
        import asyncio

        from garmin_mcp.server import _BearerAuthMiddleware

        mw = _BearerAuthMiddleware(_simple_app, "secret123")
        scope = _make_scope("Basic dXNlcjpwYXNz")
        status = asyncio.run(_collect_response(mw, scope))
        assert status == 401

    def test_non_http_scope_passed_through(self):
        """Lifespan and other non-http scopes bypass auth."""
        import asyncio

        from garmin_mcp.server import _BearerAuthMiddleware

        reached = []

        async def marker_app(scope, receive, send):
            reached.append(True)

        mw = _BearerAuthMiddleware(marker_app, "secret123")
        scope = {"type": "lifespan", "headers": []}
        asyncio.run(mw(scope, None, None))
        assert reached == [True]
