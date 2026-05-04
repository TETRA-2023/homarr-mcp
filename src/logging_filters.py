"""Logging filters used by ``server._run`` to mute known-benign upstream noise.

These filters are pure log hygiene — they neither change behaviour nor mask
real errors, only drop specific records the operator can do nothing useful
with. Each filter is scoped to a single logger and a single record shape.
"""

from __future__ import annotations

import logging

import anyio


class StandaloneSseWriterRaceFilter(logging.Filter):
    """Drop the ``mcp.server.streamable_http`` ERROR record that fires on
    session teardown when ``GET /mcp`` SSE writers race against ``DELETE
    /mcp`` cleanup.

    The upstream MCP SDK logs a full ``ClosedResourceError`` traceback from
    ``standalone_sse_writer`` (around line 711 of
    ``mcp/server/streamable_http.py``) every time a stateful client opens an
    SSE stream and immediately terminates the session — which, for our
    LiteLLM-fronted setup, is every brokered call. The DELETE itself returns
    200, the session ends cleanly, the client gets its response; the trace
    is purely log noise.

    Upstream PR #1384 (merged 2025-12-04) added explicit
    ``ClosedResourceError`` handling to the sibling ``message_router``. The
    same pattern hasn't been ported to ``standalone_sse_writer`` yet, so we
    filter the record locally rather than crank the whole logger to
    ``CRITICAL``.

    Filter is intentionally narrow: only drops records whose exact message
    matches and whose ``exc_info`` is an ``anyio.ClosedResourceError`` (or
    subclass). Every other ERROR from the same logger — including legitimate
    streamable-HTTP failures — passes through unchanged.
    """

    _MESSAGE = "Error in standalone SSE writer"

    def filter(self, record: logging.LogRecord) -> bool:
        if record.getMessage() != self._MESSAGE:
            return True
        if not record.exc_info:
            return True
        exc_type = record.exc_info[0]
        if exc_type is None:
            return True
        try:
            return not issubclass(exc_type, anyio.ClosedResourceError)
        except TypeError:
            return True
