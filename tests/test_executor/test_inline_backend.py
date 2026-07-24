"""Tests for InlineBackend (lazy capture, deferred execution)."""

import threading

import pytest

from toolregistry.executor import (
    CancelledError,
    ExecutionContext,
    HandleStatus,
    InlineBackend,
)


class TestInlineBackend:
    def test_submit_does_not_execute(self):
        """submit() only captures — status is PENDING until result()."""
        backend = InlineBackend()
        executed = []

        def work() -> int:
            executed.append(True)
            return 42

        handle = backend.submit(work, {})
        assert handle.status() == HandleStatus.PENDING
        assert executed == []
        assert handle.result() == 42
        assert handle.status() == HandleStatus.COMPLETED
        assert executed == [True]

    def test_submit_sync_function(self):
        backend = InlineBackend()

        def add(x: int, y: int) -> int:
            return x + y

        handle = backend.submit(add, {"x": 3, "y": 4})
        assert handle.result() == 7
        assert handle.status() == HandleStatus.COMPLETED

    def test_submit_async_function_sync_result(self):
        """Async fn driven via result() uses asyncio.run internally."""
        backend = InlineBackend()

        async def add(x: int, y: int) -> int:
            return x + y

        handle = backend.submit(add, {"x": 5, "y": 6})
        assert handle.result() == 11

    @pytest.mark.asyncio
    async def test_submit_async_function_async_result(self):
        """Async fn driven via result_async() is awaited natively."""
        backend = InlineBackend()

        async def add(x: int, y: int) -> int:
            return x + y

        handle = backend.submit(add, {"x": 5, "y": 6})
        assert await handle.result_async() == 11

    @pytest.mark.asyncio
    async def test_lambda_wrapping_async_fn_via_result_async(self):
        """A lambda returning a coroutine is awaited by result_async."""
        backend = InlineBackend()

        async def inner(x: int) -> int:
            return x * 2

        # Simulates ainvoke's lambda **kw: tool.arun(kw) pattern.
        handle = backend.submit(lambda **kw: inner(**kw), {"x": 21})
        assert await handle.result_async() == 42

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
        # Not yet executed (lazy) — status is PENDING.
        assert handle.status() == HandleStatus.PENDING
        with pytest.raises(ValueError, match="boom"):
            handle.result()
        assert handle.status() == HandleStatus.FAILED

    def test_cancel_before_execution(self):
        """cancel() in PENDING state prevents execution."""
        backend = InlineBackend()
        executed = []

        def work() -> int:
            executed.append(True)
            return 1

        handle = backend.submit(work, {})
        assert handle.cancel() is True
        assert handle.status() == HandleStatus.CANCELLED
        with pytest.raises(CancelledError):
            handle.result()
        assert executed == []

    def test_cancel_after_execution_returns_false(self):
        backend = InlineBackend()
        handle = backend.submit(lambda: 1, {})
        handle.result()  # execute
        assert handle.cancel() is False

    def test_on_progress_noop(self):
        backend = InlineBackend()
        handle = backend.submit(lambda: 1, {})
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
        backend.shutdown()

    def test_result_idempotent(self):
        """Calling result() twice returns the same value, no re-execution."""
        backend = InlineBackend()
        count = []

        def work() -> int:
            count.append(1)
            return 42

        handle = backend.submit(work, {})
        assert handle.result() == 42
        assert handle.result() == 42
        assert len(count) == 1
