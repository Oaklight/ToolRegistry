"""Inline execution backend — lazy capture, deferred execution."""

from __future__ import annotations

import asyncio
import inspect
import uuid
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


class InlineExecutionHandle(ExecutionHandle):
    """Handle for a lazily-captured inline execution.

    ``InlineBackend.submit`` only captures the callable and arguments;
    execution is deferred to :meth:`result` (sync) or
    :meth:`result_async` (async).

    While the handle is in the PENDING state, :meth:`cancel` can
    prevent execution entirely.
    """

    def __init__(
        self,
        exec_id: str,
        fn: Callable[..., Any],
        kwargs: dict[str, Any],
        is_async: bool,
    ) -> None:
        self._exec_id = exec_id
        self._fn = fn
        self._kwargs = kwargs
        self._is_async = is_async
        self._executed = False
        self._cancelled = False
        self._value: Any = None
        self._exception: BaseException | None = None

    @property
    def execution_id(self) -> str:
        return self._exec_id

    def cancel(self) -> bool:
        """Cancel before execution.

        Returns ``True`` if the handle was still pending and is now
        cancelled; ``False`` if it has already been executed.
        """
        if self._executed:
            return False
        self._cancelled = True
        return True

    def status(self) -> HandleStatus:
        if self._cancelled:
            return HandleStatus.CANCELLED
        if not self._executed:
            return HandleStatus.PENDING
        if isinstance(self._exception, CancelledError):
            return HandleStatus.CANCELLED
        if self._exception is not None:
            return HandleStatus.FAILED
        return HandleStatus.COMPLETED

    def result(self, timeout: float | None = None) -> Any:
        """Execute synchronously and return the result.

        Inline execution does not support ``timeout`` — the callable
        runs in the calling thread with no way to interrupt it
        externally.  The parameter is accepted for interface
        compatibility but is ignored.
        """
        if self._cancelled:
            raise CancelledError("Execution was cancelled before it started")
        if not self._executed:
            self._run_sync()
        if self._exception is not None:
            raise self._exception
        return self._value

    async def result_async(self, timeout: float | None = None) -> Any:
        """Execute and return the result, awaiting if the callable is async.

        For async callables (``tool.arun``), the coroutine is awaited
        directly on the caller's event loop — no ``asyncio.run()`` and
        no new loop.  For sync callables (``tool.run``), the function
        is called inline in the current thread.

        Detection is two-layered: ``_is_async`` (set at submit time via
        ``iscoroutinefunction``) handles ``async def`` callables, and a
        runtime ``iscoroutine`` check on the return value catches
        non-``async def`` callables that return coroutines (e.g. a
        lambda wrapping ``tool.arun``).
        """
        if self._cancelled:
            raise CancelledError("Execution was cancelled before it started")
        if not self._executed:
            if self._is_async:
                await self._run_async()
            else:
                self._run_sync()
                # A non-async-def callable (e.g. lambda wrapping
                # tool.arun) may have returned a coroutine.
                if self._exception is None and asyncio.iscoroutine(self._value):
                    try:
                        self._value = await self._value
                    except BaseException as exc:  # noqa: BLE001
                        self._exception = exc
        if self._exception is not None:
            raise self._exception
        return self._value

    def on_progress(self, callback: Callable[[ProgressReport], None]) -> None:
        pass

    def _run_sync(self) -> None:
        """Drive execution synchronously.

        For async callables, ``asyncio.run()`` is used to create a
        temporary event loop — matching the behavior of
        ``_FunctionToolWrapper.call_sync()`` for async functions.
        """
        try:
            if self._is_async:
                self._value = asyncio.run(self._fn(**self._kwargs))
            else:
                self._value = self._fn(**self._kwargs)
        except BaseException as exc:  # noqa: BLE001
            self._exception = exc
        self._executed = True

    async def _run_async(self) -> None:
        """Drive execution by awaiting the callable."""
        try:
            self._value = await self._fn(**self._kwargs)
        except BaseException as exc:  # noqa: BLE001
            self._exception = exc
        self._executed = True


class InlineBackend:
    """Execution backend that runs the callable in the current context.

    No thread or process pool is used.  ``submit()`` captures the
    callable and arguments without executing them; execution is
    deferred to ``handle.result()`` (sync) or ``handle.result_async()``
    (async).  This makes the backend usable from both sync and async
    callers without losing native async semantics.

    Inline execution does not provide process or thread isolation.
    It is suited to tools that are already isolated elsewhere
    (e.g. MCP servers, remote HTTP APIs), where pooling or pickling
    the target would be wrong or impossible.
    """

    def submit(
        self,
        fn: Callable[..., Any],
        kwargs: dict[str, Any],
        *,
        execution_id: str | None = None,
        timeout: float | None = None,
    ) -> ExecutionHandle:
        exec_id = execution_id or uuid.uuid4().hex

        # Detect whether the callable is async so the handle can choose
        # between await and direct call at execution time.
        raw_fn = getattr(fn, "fn", fn)
        is_async = inspect.iscoroutinefunction(raw_fn)

        # Context injection
        if should_inject_context(fn):
            ctx = ExecutionContext()
            kwargs = {**kwargs, "_ctx": ctx}

        return InlineExecutionHandle(exec_id, fn, kwargs, is_async)

    def shutdown(self, wait: bool = True) -> None:
        pass
