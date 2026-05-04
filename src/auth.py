"""Bearer-token authentication middleware for HTTP transports.

Pure ASGI middleware (not Starlette ``BaseHTTPMiddleware``) so streaming
responses — SSE event streams, chunked StreamableHTTP responses — pass through
without buffering.

The middleware is only mounted when running under ``streamable-http`` or
``sse`` transport AND ``MCP_BEARER_TOKEN`` is set; stdio transport never sees
it.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

logger = logging.getLogger(__name__)

ASGIApp = Callable[
    [dict[str, Any], Callable[..., Awaitable[Any]], Callable[..., Awaitable[None]]], Awaitable[None]
]

_BEARER_PREFIX = "bearer "


class BearerAuthMiddleware:
    """Reject HTTP requests lacking a matching ``Authorization: Bearer <token>``.

    Constant-time comparison via :func:`secrets.compare_digest` to defeat
    timing oracles. Lifespan and WebSocket scopes pass through unchanged.
    The ``Bearer`` scheme name is matched case-insensitively per RFC 7235 §2.1.

    Args:
        app: Downstream ASGI application.
        expected_token: Bearer token clients must present. Must be non-empty.
        skip_paths: Optional iterable of path prefixes that bypass auth (e.g.
            ``("/healthz",)``). Match is exact-or-prefix on ``scope["path"]``.
            Empty by default — every HTTP request is gated.
    """

    def __init__(
        self,
        app: ASGIApp,
        expected_token: str,
        skip_paths: Iterable[str] = (),
    ) -> None:
        if not expected_token:
            raise ValueError("expected_token must be a non-empty string")
        self._app = app
        self._expected_token = expected_token
        self._skip_paths = tuple(skip_paths)

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[Any]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        if self._skip_paths:
            path = scope.get("path", "")
            if any(path == p or path.startswith(p.rstrip("/") + "/") for p in self._skip_paths):
                await self._app(scope, receive, send)
                return

        auth_header = b""
        for name, value in scope.get("headers", ()):
            if name == b"authorization":
                auth_header = value
                break

        decoded = auth_header.decode("latin-1")
        # Scheme name is case-insensitive per RFC 7235 §2.1; the token itself
        # is opaque and compared byte-for-byte below.
        if not decoded[: len(_BEARER_PREFIX)].lower() == _BEARER_PREFIX:
            await _send_401(send)
            return

        provided = decoded[len(_BEARER_PREFIX) :]
        if not provided or not secrets.compare_digest(provided, self._expected_token):
            await _send_401(send)
            return

        await self._app(scope, receive, send)


async def _send_401(send: Callable[..., Awaitable[None]]) -> None:
    """Emit a uniform 401 response.

    The body and headers are identical regardless of which check failed —
    a client cannot distinguish "missing header" from "wrong token" from
    the response, denying that signal to attackers.
    """
    body = b'{"error":"unauthorized"}'
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b'Bearer realm="homarr-mcp"'),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})
