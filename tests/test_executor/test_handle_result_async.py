"""Tests for ExecutionHandle.result_async() across all backends."""

import asyncio
import time

import pytest

from toolregistry.executor import (
    InlineBackend,
    ProcessPoolBackend,
    ThreadBackend,
)


def _add(x: int, y: int) -> int:
    return x + y


def _fail() -> None:
    raise ValueError("boom")


def _slow() -> str:
    time.sleep(10)
    return "done"


class TestResultAsync:
    @pytest.mark.asyncio
    async def test_thread_result_async(self):
        backend = ThreadBackend(max_workers=2)
        try:
            handle = backend.submit(_add, {"x": 3, "y": 4})
            assert await handle.result_async() == 7
        finally:
            backend.shutdown()

    @pytest.mark.asyncio
    async def test_process_result_async(self):
        backend = ProcessPoolBackend(max_workers=2)
        try:
            handle = backend.submit(_add, {"x": 10, "y": 20})
            assert await handle.result_async() == 30
        finally:
            backend.shutdown()

    @pytest.mark.asyncio
    async def test_inline_result_async(self):
        backend = InlineBackend()
        handle = backend.submit(_add, {"x": 1, "y": 2})
        assert await handle.result_async() == 3

    @pytest.mark.asyncio
    async def test_thread_result_async_propagates_exception(self):
        backend = ThreadBackend(max_workers=2)
        try:
            handle = backend.submit(_fail, {})
            with pytest.raises(ValueError, match="boom"):
                await handle.result_async()
        finally:
            backend.shutdown()

    @pytest.mark.asyncio
    async def test_inline_result_async_propagates_exception(self):
        backend = InlineBackend()
        handle = backend.submit(_fail, {})
        with pytest.raises(ValueError, match="boom"):
            await handle.result_async()

    @pytest.mark.asyncio
    async def test_thread_result_async_timeout(self):
        backend = ThreadBackend(max_workers=2)
        try:
            handle = backend.submit(_slow, {}, timeout=0.05)
            with pytest.raises(TimeoutError):
                await handle.result_async()
        finally:
            backend.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_result_async_does_not_block_loop(self):
        """Two overlapping thread submits both complete under gather.

        If result_async blocked the event loop, the total wall time
        would be ~2x a single sleep; gathered it should be ~1x.
        """
        backend = ThreadBackend(max_workers=4)
        try:

            def sleeper(n: int) -> int:
                time.sleep(0.2)
                return n

            h1 = backend.submit(sleeper, {"n": 1})
            h2 = backend.submit(sleeper, {"n": 2})

            start = time.perf_counter()
            results = await asyncio.gather(h1.result_async(), h2.result_async())
            elapsed = time.perf_counter() - start

            assert set(results) == {1, 2}
            # Concurrent execution: well under the 0.4s serial lower bound.
            assert elapsed < 0.35
        finally:
            backend.shutdown()
