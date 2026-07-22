"""Tests for the shared AsyncRuntime."""

import asyncio
import threading

import pytest

from toolregistry._async_runtime import AsyncRuntime


@pytest.fixture(autouse=True)
def _clean_runtime():
    """Ensure a fresh runtime for each test."""
    yield
    AsyncRuntime.shutdown()


class TestAsyncRuntime:
    """Tests for AsyncRuntime class-level singleton."""

    def test_run_sync_basic(self):
        """run_sync executes a coroutine and returns its result."""

        async def add(a: int, b: int) -> int:
            return a + b

        assert AsyncRuntime.run_sync(add(2, 3)) == 5

    def test_run_sync_propagates_exception(self):
        """run_sync propagates exceptions from the coroutine."""

        async def fail():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            AsyncRuntime.run_sync(fail())

    def test_get_loop_returns_running_loop(self):
        """get_loop returns a running event loop."""
        loop = AsyncRuntime.get_loop()
        assert loop.is_running()

    def test_get_loop_returns_same_loop(self):
        """Multiple calls return the same loop instance."""
        loop1 = AsyncRuntime.get_loop()
        loop2 = AsyncRuntime.get_loop()
        assert loop1 is loop2

    def test_shared_loop_across_sequential_calls(self):
        """Sequential run_sync calls share the same event loop.

        This is the core fix: previously each sync registration
        created and destroyed its own loop, breaking anyio state.
        """
        loop_ids: list[int] = []

        async def capture_loop_id() -> int:
            loop = asyncio.get_running_loop()
            return id(loop)

        loop_ids.append(AsyncRuntime.run_sync(capture_loop_id()))
        loop_ids.append(AsyncRuntime.run_sync(capture_loop_id()))
        loop_ids.append(AsyncRuntime.run_sync(capture_loop_id()))

        assert len(set(loop_ids)) == 1, "All calls should use the same loop"

    def test_thread_safety(self):
        """Concurrent get_loop calls from multiple threads return the same loop."""
        loops: list[asyncio.AbstractEventLoop] = []
        barrier = threading.Barrier(4)

        def grab_loop():
            barrier.wait()
            loops.append(AsyncRuntime.get_loop())

        threads = [threading.Thread(target=grab_loop) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(loops) == 4
        assert all(loop is loops[0] for loop in loops)

    def test_shutdown_and_restart(self):
        """After shutdown, the next call lazily creates a new loop."""
        loop1 = AsyncRuntime.get_loop()
        AsyncRuntime.shutdown()

        # Loop should be stopped/closed after shutdown.
        assert not loop1.is_running()

        # Next call creates a new loop.
        loop2 = AsyncRuntime.get_loop()
        assert loop2.is_running()
        assert loop2 is not loop1

    def test_shutdown_idempotent(self):
        """Calling shutdown multiple times is safe."""
        AsyncRuntime.shutdown()
        AsyncRuntime.shutdown()
        AsyncRuntime.shutdown()
        # Should still work after.
        assert AsyncRuntime.run_sync(asyncio.sleep(0, result=42)) == 42

    def test_async_state_survives_across_calls(self):
        """Async state (e.g. a dict mutated by coroutines) persists
        across sequential run_sync calls on the shared loop.

        This validates that anyio/async resources are not torn down
        between calls, which was the original bug.
        """
        shared: dict[str, int] = {}

        async def set_value(key: str, val: int):
            shared[key] = val

        async def get_value(key: str) -> int:
            return shared[key]

        AsyncRuntime.run_sync(set_value("x", 10))
        result = AsyncRuntime.run_sync(get_value("x"))
        assert result == 10
