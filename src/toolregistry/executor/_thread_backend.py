"""Thread-pool execution backend with cooperative cancellation."""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any
from collections.abc import Callable

from ._helpers import should_inject_context
from ._protocol import ExecutionHandle
from ._types import (
    CancelledError,
    ExecutionContext,
    HandleStatus,
    ProgressReport,
)


class ThreadExecutionHandle(ExecutionHandle):
    """Handle wrapping a ThreadPoolExecutor Future."""

    def __init__(
        self,
        future: Future,
        exec_id: str,
        ctx: ExecutionContext | None,
        timeout: float | None,
    ) -> None:
        self._future = future
        self._exec_id = exec_id
        self._ctx = ctx
        self._timeout = timeout

    @property
    def execution_id(self) -> str:
        return self._exec_id

    def cancel(self) -> bool:
        """Request cancellation.

        Tries to cancel the future before it starts, and signals
        cooperative cancellation via the execution context.
        """
        cancelled = self._future.cancel()
        if self._ctx is not None:
            self._ctx._request_cancel()
        return cancelled or (self._ctx is not None)

    def status(self) -> HandleStatus:
        if self._future.cancelled():
            return HandleStatus.CANCELLED
        if self._future.running():
            return HandleStatus.RUNNING
        if self._future.done():
            exc = self._future.exception(timeout=0)
            if isinstance(exc, CancelledError):
                return HandleStatus.CANCELLED
            if exc is not None:
                return HandleStatus.FAILED
            return HandleStatus.COMPLETED
        return HandleStatus.PENDING

    def result(self, timeout: float | None = None) -> Any:
        effective_timeout = timeout if timeout is not None else self._timeout
        try:
            return self._future.result(timeout=effective_timeout)
        except FuturesTimeoutError as e:
            raise TimeoutError(str(e)) from e

    async def result_async(self, timeout: float | None = None) -> Any:
        effective_timeout = timeout if timeout is not None else self._timeout
        fut = asyncio.wrap_future(self._future)
        try:
            if effective_timeout is not None:
                return await asyncio.wait_for(fut, effective_timeout)
            return await fut
        except (asyncio.TimeoutError, FuturesTimeoutError) as e:
            raise TimeoutError(str(e)) from e

    def on_progress(self, callback: Callable[[ProgressReport], None]) -> None:
        if self._ctx is not None:
            self._ctx._add_progress_listener(callback)


class ThreadBackend:
    """Execution backend using a thread pool with cooperative cancellation.

    Cancellation works via ``threading.Event`` inside ``ExecutionContext``.
    Tool functions that accept ``_ctx: ExecutionContext`` can poll
    ``_ctx.cancelled`` or call ``_ctx.check_cancelled()`` to cooperate.
    """

    def __init__(self, max_workers: int | None = None) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers)

    def submit(
        self,
        fn: Callable[..., Any],
        kwargs: dict[str, Any],
        *,
        execution_id: str | None = None,
        timeout: float | None = None,
    ) -> ExecutionHandle:
        exec_id = execution_id or uuid.uuid4().hex

        # Wrap bare async functions so they can run in the thread pool.
        # For tool wrappers, unwrap to the inner function for the check;
        # for bare async callables passed directly, wrap them in-place.
        raw_fn = getattr(fn, "fn", fn)
        if asyncio.iscoroutinefunction(raw_fn) and not hasattr(fn, "call_sync"):
            async_fn = fn

            def _sync_wrapper(**kw):  # type: ignore[no-untyped-def]
                return asyncio.run(async_fn(**kw))

            fn = _sync_wrapper

        # Context injection
        ctx: ExecutionContext | None = None
        if should_inject_context(fn):
            ctx = ExecutionContext()
            kwargs = {**kwargs, "_ctx": ctx}

        future = self._pool.submit(fn, **kwargs)
        return ThreadExecutionHandle(future, exec_id, ctx, timeout)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
