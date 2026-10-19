"""Tests for ProcessPoolBackend."""

import pytest

from toolregistry.executor import (
    HandleStatus,
    ProcessPoolBackend,
    UnpicklableResultError,
)


def _add(x: int, y: int) -> int:
    """Module-level function (picklable)."""
    return x + y


def _fail() -> None:
    """Module-level function that raises."""
    raise ValueError("process boom")


def _returns_generator():
    """Module-level function returning a value that cannot be pickled."""
    return (x for x in (1, 2))


def _raises_lookalike() -> None:
    """Raise a pickling-looking error from inside the tool itself."""
    raise TypeError("cannot pickle 'generator' object")


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

    def test_unpicklable_result_raises_actionable_error(self):
        backend = ProcessPoolBackend(max_workers=2)
        try:
            handle = backend.submit(_returns_generator, {})
            with pytest.raises(UnpicklableResultError) as excinfo:
                handle.result(timeout=10)
        finally:
            backend.shutdown()

        message = str(excinfo.value)
        assert "must pickle the tool result" in message
        assert "thread backend" in message
        # The original pickling failure is preserved for diagnosis.
        assert "cannot pickle 'generator' object" in message
        # The original exception remains available through the chain.
        assert isinstance(excinfo.value.__cause__, TypeError)

    @pytest.mark.asyncio
    async def test_unpicklable_result_async_raises_actionable_error(self):
        backend = ProcessPoolBackend(max_workers=2)
        try:
            handle = backend.submit(_returns_generator, {})
            with pytest.raises(UnpicklableResultError) as excinfo:
                await handle.result_async(timeout=10)
        finally:
            backend.shutdown()

        assert "must pickle the tool result" in str(excinfo.value)

    def test_tool_raised_lookalike_error_is_not_translated(self):
        backend = ProcessPoolBackend(max_workers=2)
        try:
            handle = backend.submit(_raises_lookalike, {})
            with pytest.raises(TypeError) as excinfo:
                handle.result(timeout=10)
        finally:
            backend.shutdown()

        # A tool that raises a similar message is not a boundary failure.
        assert not isinstance(excinfo.value, UnpicklableResultError)

    def test_shutdown(self):
        backend = ProcessPoolBackend(max_workers=1)
        backend.shutdown()  # should not raise
