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


def _raises_lookalike_naming_frame() -> None:
    """Raise a lookalike whose message names the sendback frame."""
    raise TypeError("failed near _sendback_result")


def _raises_lookalike_with_fake_frame() -> None:
    """Raise a lookalike whose message embeds a whole fake frame line."""
    raise TypeError(
        'boom\n  File "/x/concurrent/futures/process.py", line 42, in _sendback_result'
    )


class _UnpicklablePayloadError(Exception):
    """Exception whose own attribute makes it unpicklable."""

    def __init__(self, message: str) -> None:
        super().__init__(message)

        def payload(x: int) -> int:
            return x

        self.payload = payload


def _raises_unpicklable_exception() -> None:
    """Raise an exception that cannot be pickled back to the parent."""
    raise _UnpicklablePayloadError("boom with an unpicklable payload")


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

    def test_tool_message_naming_sendback_frame_is_not_translated(self):
        """Tool-controlled text must not decide the classification."""
        backend = ProcessPoolBackend(max_workers=2)
        try:
            handle = backend.submit(_raises_lookalike_naming_frame, {})
            with pytest.raises(TypeError) as excinfo:
                handle.result(timeout=10)
        finally:
            backend.shutdown()

        assert not isinstance(excinfo.value, UnpicklableResultError)
        assert "failed near _sendback_result" in str(excinfo.value)

    def test_tool_message_with_fake_frame_is_not_translated(self):
        """Even an embedded frame line must not spoof the boundary check."""
        backend = ProcessPoolBackend(max_workers=2)
        try:
            handle = backend.submit(_raises_lookalike_with_fake_frame, {})
            with pytest.raises(TypeError) as excinfo:
                handle.result(timeout=10)
        finally:
            backend.shutdown()

        assert not isinstance(excinfo.value, UnpicklableResultError)

    def test_unpicklable_exception_is_translated(self):
        """The tool's exception, not just its result, must cross the boundary."""
        backend = ProcessPoolBackend(max_workers=2)
        try:
            handle = backend.submit(_raises_unpicklable_exception, {})
            with pytest.raises(UnpicklableResultError) as excinfo:
                handle.result(timeout=10)
        finally:
            backend.shutdown()

        assert "tool's exception" in str(excinfo.value)
        # The serialization failure, not the tool's own exception class,
        # could not cross the boundary.  CPython raises AttributeError
        # through 3.13 and PicklingError from 3.14, so assert on the
        # meaning (the local object that could not be pickled), not the
        # serializer's exception class.
        assert not isinstance(excinfo.value.__cause__, _UnpicklablePayloadError)
        assert "Can't pickle local object" in str(excinfo.value.__cause__)

    def test_shutdown(self):
        backend = ProcessPoolBackend(max_workers=1)
        backend.shutdown()  # should not raise

    def test_pool_avoids_fork_start_method(self):
        """Workers must not be forked from a potentially threaded parent."""
        from toolregistry.executor._process_backend import _pool_context

        assert _pool_context().get_start_method() in {"forkserver", "spawn"}
