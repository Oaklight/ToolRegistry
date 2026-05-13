"""Tests for ProcessPoolBackend."""

import pytest

from toolregistry.executor import (
    HandleStatus,
    ProcessPoolBackend,
)


def _add(x: int, y: int) -> int:
    """Module-level function (picklable)."""
    return x + y


def _fail() -> None:
    """Module-level function that raises."""
    raise ValueError("process boom")


class TestProcessPoolBackend:
    def test_submit_sync_function(self):
        backend = ProcessPoolBackend(max_workers=2)
        try:
            handle = backend.submit(_add, {"x": 3, "y": 4})
            assert handle.result(timeout=10) == 7
            assert handle.status() == HandleStatus.COMPLETED
        finally:
            backend.shutdown()

    def test_submit_async_function(self):
        backend = ProcessPoolBackend(max_workers=2)
        try:

            async def async_add(x: int, y: int) -> int:
                return x + y

            handle = backend.submit(async_add, {"x": 5, "y": 6})
            assert handle.result(timeout=10) == 11
        finally:
            backend.shutdown()

    def test_status_failed(self):
        backend = ProcessPoolBackend(max_workers=2)
        try:
            handle = backend.submit(_fail, {})
            with pytest.raises(ValueError, match="process boom"):
                handle.result(timeout=10)
            assert handle.status() == HandleStatus.FAILED
        finally:
            backend.shutdown()

    def test_on_progress_noop(self):
        backend = ProcessPoolBackend(max_workers=1)
        try:
            handle = backend.submit(_add, {"x": 1, "y": 2})
            handle.on_progress(lambda r: None)  # should not raise
            handle.result(timeout=10)
        finally:
            backend.shutdown()

    def test_execution_id(self):
        backend = ProcessPoolBackend(max_workers=1)
        try:
            handle = backend.submit(_add, {"x": 1, "y": 2}, execution_id="proc-1")
            assert handle.execution_id == "proc-1"
            handle.result(timeout=10)
        finally:
            backend.shutdown()

    def test_shutdown(self):
        backend = ProcessPoolBackend(max_workers=1)
        backend.shutdown()  # should not raise
