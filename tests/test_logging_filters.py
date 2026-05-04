"""Tests for ``src.logging_filters.StandaloneSseWriterRaceFilter``."""

from __future__ import annotations

import logging
import sys

import anyio
import pytest

from src.logging_filters import StandaloneSseWriterRaceFilter


def _make_record(
    message: str,
    *,
    exc_info: tuple | None = None,
) -> logging.LogRecord:
    return logging.LogRecord(
        name="mcp.server.streamable_http",
        level=logging.ERROR,
        pathname=__file__,
        lineno=0,
        msg=message,
        args=(),
        exc_info=exc_info,
    )


def _exc_info_for(exc: BaseException) -> tuple:
    try:
        raise exc
    except BaseException:
        return sys.exc_info()


class TestStandaloneSseWriterRaceFilter:
    def setup_method(self) -> None:
        self.filt = StandaloneSseWriterRaceFilter()

    def test_passes_unrelated_message(self) -> None:
        rec = _make_record("Some other error", exc_info=_exc_info_for(anyio.ClosedResourceError()))
        assert self.filt.filter(rec) is True

    def test_passes_target_message_without_exc_info(self) -> None:
        rec = _make_record("Error in standalone SSE writer")
        assert self.filt.filter(rec) is True

    def test_passes_target_message_with_unrelated_exc(self) -> None:
        rec = _make_record(
            "Error in standalone SSE writer",
            exc_info=_exc_info_for(RuntimeError("totally different")),
        )
        assert self.filt.filter(rec) is True

    def test_drops_target_message_with_closed_resource_error(self) -> None:
        rec = _make_record(
            "Error in standalone SSE writer",
            exc_info=_exc_info_for(anyio.ClosedResourceError()),
        )
        assert self.filt.filter(rec) is False

    def test_drops_subclass_of_closed_resource_error(self) -> None:
        class _SubError(anyio.ClosedResourceError):
            pass

        rec = _make_record(
            "Error in standalone SSE writer",
            exc_info=_exc_info_for(_SubError()),
        )
        assert self.filt.filter(rec) is False

    def test_handles_malformed_exc_info_gracefully(self) -> None:
        """exc_info[0] = None can happen on some logging shapes — must not raise."""
        rec = _make_record("Error in standalone SSE writer", exc_info=(None, None, None))
        assert self.filt.filter(rec) is True


@pytest.mark.parametrize(
    "msg",
    [
        "error in standalone sse writer",
        "Error in standalone SSE writer (extra)",
        "Standalone SSE writer error",
    ],
)
def test_message_match_is_exact(msg: str) -> None:
    """Filter intentionally matches only the exact upstream message string —
    a future upstream wording change should bring the noise back, not mask it."""
    filt = StandaloneSseWriterRaceFilter()
    rec = _make_record(msg, exc_info=_exc_info_for(anyio.ClosedResourceError()))
    assert filt.filter(rec) is True
