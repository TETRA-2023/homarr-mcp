"""Tests for the bearer-token authentication middleware."""

from __future__ import annotations

from typing import Any

import pytest

from src.auth import BearerAuthMiddleware


class _Recorder:
    """Capture ASGI ``send`` events into a list."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def __call__(self, message: dict[str, Any]) -> None:
        self.events.append(message)


async def _ok_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    """Toy downstream ASGI app — emits a 200 with body 'ok'."""
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"ok", "more_body": False})


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


def _http_scope(authorization: bytes | None = None) -> dict[str, Any]:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization))
    return {"type": "http", "method": "POST", "path": "/mcp", "headers": headers}


class TestBearerAuthMiddleware:
    def test_construction_rejects_empty_token(self) -> None:
        with pytest.raises(ValueError):
            BearerAuthMiddleware(_ok_app, expected_token="")

    @pytest.mark.asyncio
    async def test_accepts_matching_token(self) -> None:
        mw = BearerAuthMiddleware(_ok_app, expected_token="s3cret")
        send = _Recorder()
        await mw(_http_scope(b"Bearer s3cret"), _noop_receive, send)
        assert send.events[0]["status"] == 200
        assert send.events[1]["body"] == b"ok"

    @pytest.mark.asyncio
    async def test_rejects_missing_header(self) -> None:
        mw = BearerAuthMiddleware(_ok_app, expected_token="s3cret")
        send = _Recorder()
        await mw(_http_scope(authorization=None), _noop_receive, send)
        assert send.events[0]["status"] == 401
        assert any(
            h == (b"www-authenticate", b'Bearer realm="homarr-mcp"')
            for h in send.events[0]["headers"]
        )

    @pytest.mark.asyncio
    async def test_rejects_wrong_scheme(self) -> None:
        mw = BearerAuthMiddleware(_ok_app, expected_token="s3cret")
        send = _Recorder()
        await mw(_http_scope(b"Basic dXNlcjpwYXNz"), _noop_receive, send)
        assert send.events[0]["status"] == 401

    @pytest.mark.asyncio
    async def test_rejects_wrong_token(self) -> None:
        mw = BearerAuthMiddleware(_ok_app, expected_token="s3cret")
        send = _Recorder()
        await mw(_http_scope(b"Bearer wrong"), _noop_receive, send)
        assert send.events[0]["status"] == 401

    @pytest.mark.asyncio
    async def test_passes_lifespan_through(self) -> None:
        seen: list[str] = []

        async def lifespan_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            seen.append(scope["type"])

        mw = BearerAuthMiddleware(lifespan_app, expected_token="s3cret")
        await mw({"type": "lifespan"}, _noop_receive, _Recorder())
        assert seen == ["lifespan"]

    @pytest.mark.asyncio
    async def test_passes_websocket_through(self) -> None:
        seen: list[str] = []

        async def ws_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            seen.append(scope["type"])

        mw = BearerAuthMiddleware(ws_app, expected_token="s3cret")
        await mw({"type": "websocket", "headers": []}, _noop_receive, _Recorder())
        assert seen == ["websocket"]
