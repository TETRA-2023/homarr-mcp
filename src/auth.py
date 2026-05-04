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
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

ASGIApp = Callable[
    [dict[str, Any], Callable[..., Awaitable[Any]], Callable[..., Awaitable[None]]], Awaitable[None]
]


class BearerAuthMiddleware:
    """Reject HTTP requests lacking a matching ``Authorization: Bearer <token>``.

    Constant-time comparison via :func:`secrets.compare_digest` to defeat
    timing oracles. Lifespan and WebSocket scopes pass through unchanged.
    """

    def __init__(self, app: ASGIApp, expected_token: str) -> None:
        if not expected_token:
            raise ValueError("expected_token must be a non-empty string")
        self._app = app
        self._expected_token = expected_token

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[Any]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        auth_header = b""
        for name, value in scope.get("headers", ()):
            if name == b"authorization":
                auth_header = value
                break

        decoded = auth_header.decode("latin-1")
        if not decoded.startswith("Bearer "):
            await _send_401(send, "missing or malformed Authorization header")
            return

        provided = decoded[len("Bearer ") :]
        if not secrets.compare_digest(provided, self._expected_token):
            await _send_401(send, "invalid bearer token")
            return

        await self._app(scope, receive, send)


async def _send_401(send: Callable[..., Awaitable[None]], reason: str) -> None:
    body = b'{"error":"unauthorized"}'
    logger.info("Rejecting request: %s", reason)
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
