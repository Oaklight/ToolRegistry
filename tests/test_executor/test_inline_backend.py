"""Tests for InlineBackend."""

import pytest

from toolregistry.executor import (
    ExecutionContext,
    HandleStatus,
    InlineBackend,
)


class TestInlineBackend:
    def test_submit_sync_function(self):
        backend = InlineBackend()

        def add(x: int, y: int) -> int:
            return x + y

        handle = backend.submit(add, {"x": 3, "y": 4})
        assert handle.result() == 7
        assert handle.status() == HandleStatus.COMPLETED

    def test_submit_async_function(self):
        backend = InlineBackend()

        async def add(x: int, y: int) -> int:
            return x + y

        handle = backend.submit(add, {"x": 5, "y": 6})
        assert handle.result() == 11

    def test_context_injection(self):
        backend = InlineBackend()

        def work(x: int, _ctx: ExecutionContext) -> str:
            return f"got {x}, ctx={_ctx is not None}"

        handle = backend.submit(work, {"x": 42})
        assert handle.result() == "got 42, ctx=True"

    def test_status_failed_and_result_reraises(self):
        backend = InlineBackend()

        def fail() -> None:
            raise ValueError("boom")

        handle = backend.submit(fail, {})
        assert handle.status() == HandleStatus.FAILED
        with pytest.raises(ValueError, match="boom"):
            handle.result()

    def test_cancel_returns_false(self):
        backend = InlineBackend()
        handle = backend.submit(lambda: 1, {})
        assert handle.cancel() is False

    def test_on_progress_noop(self):
        backend = InlineBackend()
        handle = backend.submit(lambda: 1, {})
        # Should not raise even though inline has no progress support.
        handle.on_progress(lambda r: None)
        assert handle.result() == 1

    def test_execution_id_provided(self):
        backend = InlineBackend()
        handle = backend.submit(lambda: 1, {}, execution_id="my-id")
        assert handle.execution_id == "my-id"

    def test_execution_id_generated(self):
        backend = InlineBackend()
        handle = backend.submit(lambda: 1, {})
        assert len(handle.execution_id) > 0

    def test_runs_in_calling_thread(self):
        import threading

        backend = InlineBackend()
        caller_thread = threading.get_ident()
        captured: dict[str, int] = {}

        def work() -> int:
            captured["thread"] = threading.get_ident()
            return 1

        backend.submit(work, {}).result()
        assert captured["thread"] == caller_thread

    def test_shutdown_noop(self):
        backend = InlineBackend()
        backend.shutdown()  # should not raise

    def test_bare_async_from_sync_context_runs(self):
        """A bare async callable runs fine when no loop is active."""
        backend = InlineBackend()

        async def double(x: int) -> int:
            return x * 2

        handle = backend.submit(double, {"x": 21})
        assert handle.result() == 42

    @pytest.mark.asyncio
    async def test_bare_async_from_running_loop_raises_clear_error(self):
        """Submitting a bare async callable inside a running loop raises.

        InlineBackend drives bare coroutines via ``asyncio.run``, which
        cannot run under an active loop.  It should fail fast with a
        clear message rather than an opaque RuntimeError.
        """
        backend = InlineBackend()

        async def double(x: int) -> int:
            return x * 2

        # The exception is captured at submit and re-raised on result().
        handle = backend.submit(double, {"x": 21})
        with pytest.raises(RuntimeError, match="event loop is already running"):
            handle.result()
