"""Wiring tests for ``server._run`` — confirm middleware attachment.

These tests do not start uvicorn; they patch ``uvicorn.Server`` and capture
the ASGI app that ``_run`` would have served. That is enough to verify the
control flow: stdio bypasses uvicorn entirely; HTTP transports wrap the app
when ``MCP_BEARER_TOKEN`` is set and pass the bare app through otherwise.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

import src.server as server_mod
from src.auth import BearerAuthMiddleware
from src.logging_filters import StandaloneSseWriterRaceFilter


def _fake_settings(*, has_token: bool, token: str = "s3cret") -> MagicMock:
    """Build a stand-in for ``HomarrSettings`` (a frozen pydantic model that
    rejects ``patch.object`` on its fields)."""
    s = MagicMock()
    s.has_bearer_token = has_token
    s.get_bearer_token_value = MagicMock(return_value=token)
    return s


@contextmanager
def _patched_uvicorn():
    """Patch the uvicorn import inside ``server._run`` so .run() never blocks."""
    fake_uvicorn = MagicMock()
    fake_uvicorn.Server.return_value.run = MagicMock(return_value=None)
    with patch.dict("sys.modules", {"uvicorn": fake_uvicorn}):
        yield fake_uvicorn


def _captured_app(fake_uvicorn: MagicMock):
    """Pull the ASGI app argument out of the recorded ``uvicorn.Config`` call."""
    fake_uvicorn.Config.assert_called_once()
    args, kwargs = fake_uvicorn.Config.call_args
    return args[0] if args else kwargs["app"]


class TestRunDispatch:
    def test_stdio_does_not_touch_uvicorn(self) -> None:
        with _patched_uvicorn() as fake_uvicorn, patch.object(server_mod.mcp, "run") as fake_run:
            server_mod._run("stdio")
        fake_run.assert_called_once_with(transport="stdio")
        fake_uvicorn.Config.assert_not_called()
        fake_uvicorn.Server.assert_not_called()

    def test_streamable_http_without_token_passes_bare_app(self) -> None:
        bare_app = object()
        with (
            patch.object(server_mod.mcp, "streamable_http_app", return_value=bare_app),
            patch.object(server_mod, "settings", _fake_settings(has_token=False)),
            _patched_uvicorn() as fake_uvicorn,
        ):
            server_mod._run("streamable-http")
        assert _captured_app(fake_uvicorn) is bare_app

    def test_streamable_http_with_token_wraps_with_middleware(self) -> None:
        bare_app = object()
        with (
            patch.object(server_mod.mcp, "streamable_http_app", return_value=bare_app),
            patch.object(server_mod, "settings", _fake_settings(has_token=True)),
            _patched_uvicorn() as fake_uvicorn,
        ):
            server_mod._run("streamable-http")
        wrapped = _captured_app(fake_uvicorn)
        assert isinstance(wrapped, BearerAuthMiddleware)
        assert wrapped._app is bare_app
        assert wrapped._expected_token == "s3cret"

    def test_sse_with_token_wraps_with_middleware(self) -> None:
        bare_app = object()
        with (
            patch.object(server_mod.mcp, "sse_app", return_value=bare_app),
            patch.object(server_mod, "settings", _fake_settings(has_token=True)),
            _patched_uvicorn() as fake_uvicorn,
        ):
            server_mod._run("sse")
        wrapped = _captured_app(fake_uvicorn)
        assert isinstance(wrapped, BearerAuthMiddleware)
        assert wrapped._app is bare_app


class TestRunWarning:
    def test_warns_when_token_missing(self, caplog: pytest.LogCaptureFixture) -> None:
        bare_app = object()
        with (
            patch.object(server_mod.mcp, "streamable_http_app", return_value=bare_app),
            patch.object(server_mod, "settings", _fake_settings(has_token=False)),
            _patched_uvicorn(),
        ):
            with caplog.at_level("WARNING", logger="src.server"):
                server_mod._run("streamable-http")
        assert any(
            "MCP_BEARER_TOKEN not set" in rec.message and rec.levelname == "WARNING"
            for rec in caplog.records
        )


@pytest.fixture
def _clean_sdk_logger_filters():
    """Strip our race filter from the upstream logger before + after each test
    so order-of-execution doesn't leak attachment state across cases."""
    sdk_logger = logging.getLogger("mcp.server.streamable_http")

    def _purge() -> None:
        for f in list(sdk_logger.filters):
            if isinstance(f, StandaloneSseWriterRaceFilter):
                sdk_logger.removeFilter(f)

    _purge()
    try:
        yield sdk_logger
    finally:
        _purge()


class TestRaceFilterInstallation:
    def test_attaches_race_filter_on_http_transport(
        self, _clean_sdk_logger_filters: logging.Logger
    ) -> None:
        bare_app = object()
        with (
            patch.object(server_mod.mcp, "streamable_http_app", return_value=bare_app),
            patch.object(server_mod, "settings", _fake_settings(has_token=False)),
            _patched_uvicorn(),
        ):
            server_mod._run("streamable-http")
        assert any(
            isinstance(f, StandaloneSseWriterRaceFilter) for f in _clean_sdk_logger_filters.filters
        )

    def test_does_not_attach_on_stdio(self, _clean_sdk_logger_filters: logging.Logger) -> None:
        with _patched_uvicorn(), patch.object(server_mod.mcp, "run"):
            server_mod._run("stdio")
        assert not any(
            isinstance(f, StandaloneSseWriterRaceFilter) for f in _clean_sdk_logger_filters.filters
        )

    def test_attachment_is_idempotent(self, _clean_sdk_logger_filters: logging.Logger) -> None:
        bare_app = object()
        with (
            patch.object(server_mod.mcp, "streamable_http_app", return_value=bare_app),
            patch.object(server_mod, "settings", _fake_settings(has_token=False)),
            _patched_uvicorn(),
        ):
            server_mod._run("streamable-http")
            server_mod._run("streamable-http")
        race_filters = [
            f
            for f in _clean_sdk_logger_filters.filters
            if isinstance(f, StandaloneSseWriterRaceFilter)
        ]
        assert len(race_filters) == 1
