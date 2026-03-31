"""Tests for ThreadBackend."""

import time
import threading

import pytest

from toolregistry.executor import (
    ExecutionContext,
    ExecutionStatus,
    ThreadBackend,
)


class TestThreadBackend:
    def test_submit_sync_function(self):
        backend = ThreadBackend(max_workers=2)
        try:

            def add(x: int, y: int) -> int:
                return x + y

            handle = backend.submit(add, {"x": 3, "y": 4})
            assert handle.result() == 7
            assert handle.status() == ExecutionStatus.COMPLETED
        finally:
            backend.shutdown()

    def test_submit_async_function(self):
        backend = ThreadBackend(max_workers=2)
        try:

            async def add(x: int, y: int) -> int:
                return x + y

            handle = backend.submit(add, {"x": 5, "y": 6})
            assert handle.result() == 11
        finally:
            backend.shutdown()

    def test_context_injection(self):
        backend = ThreadBackend(max_workers=2)
        try:

            def work(x: int, _ctx: ExecutionContext) -> str:
                return f"got {x}, ctx={_ctx is not None}"

            handle = backend.submit(work, {"x": 42})
            assert handle.result() == "got 42, ctx=True"
        finally:
            backend.shutdown()

    def test_cooperative_cancel(self):
        backend = ThreadBackend(max_workers=2)
        try:
            started = threading.Event()

            def slow_work(x: int, _ctx: ExecutionContext) -> str:
                started.set()
                while not _ctx.cancelled:
                    time.sleep(0.01)
                return "cancelled"

            handle = backend.submit(slow_work, {"x": 1})
            started.wait(timeout=2)
            handle.cancel()
            result = handle.result(timeout=2)
            assert result == "cancelled"
        finally:
            backend.shutdown()

    def test_status_failed(self):
        backend = ThreadBackend(max_workers=2)
        try:

            def fail() -> None:
                raise ValueError("boom")

            handle = backend.submit(fail, {})
            with pytest.raises(ValueError, match="boom"):
                handle.result(timeout=2)
            assert handle.status() == ExecutionStatus.FAILED
        finally:
            backend.shutdown()

    def test_result_timeout(self):
        backend = ThreadBackend(max_workers=2)
        try:

            def slow() -> str:
                time.sleep(10)
                return "done"

            handle = backend.submit(slow, {}, timeout=0.05)
            with pytest.raises(TimeoutError):
                handle.result()
        finally:
            backend.shutdown(wait=False)

    def test_on_progress(self):
        backend = ThreadBackend(max_workers=2)
        try:
            reports = []
            started = threading.Event()

            def work_with_progress(x: int, _ctx: ExecutionContext) -> str:
                started.wait(timeout=2)  # wait for listener to be registered
                _ctx.report_progress(fraction=0.5, message="halfway")
                _ctx.report_progress(fraction=1.0, message="done")
                return "result"

            handle = backend.submit(work_with_progress, {"x": 1})
            handle.on_progress(lambda r: reports.append(r))
            started.set()  # allow the function to proceed
            result = handle.result(timeout=5)
            assert result == "result"
            assert len(reports) == 2
            assert reports[0].fraction == 0.5
            assert reports[1].fraction == 1.0
        finally:
            backend.shutdown()

    def test_execution_id_provided(self):
        backend = ThreadBackend(max_workers=1)
        try:
            handle = backend.submit(lambda: 1, {}, execution_id="my-id")
            assert handle.execution_id == "my-id"
            handle.result(timeout=2)
        finally:
            backend.shutdown()

    def test_execution_id_generated(self):
        backend = ThreadBackend(max_workers=1)
        try:
            handle = backend.submit(lambda: 1, {})
            assert len(handle.execution_id) > 0
            handle.result(timeout=2)
        finally:
            backend.shutdown()

    def test_multiple_concurrent(self):
        backend = ThreadBackend(max_workers=4)
        try:

            def compute(n: int) -> int:
                return n * n

            handles = [backend.submit(compute, {"n": i}) for i in range(10)]
            results = [h.result(timeout=5) for h in handles]
            assert results == [i * i for i in range(10)]
        finally:
            backend.shutdown()

    def test_shutdown(self):
        backend = ThreadBackend(max_workers=1)
        backend.shutdown()  # should not raise
