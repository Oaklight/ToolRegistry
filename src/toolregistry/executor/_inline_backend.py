"""Inline execution backend that runs the target in the current context."""

from __future__ import annotations

import asyncio
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
    """Handle wrapping an already-completed inline execution.

    ``InlineBackend.submit`` runs the callable eagerly, so the handle
    is created in a terminal state carrying either a captured return
    value or a captured exception.
    """

    def __init__(
        self,
        exec_id: str,
        value: Any = None,
        exception: BaseException | None = None,
    ) -> None:
        self._exec_id = exec_id
        self._value = value
        self._exception = exception

    @property
    def execution_id(self) -> str:
        return self._exec_id

    def cancel(self) -> bool:
        # Execution already finished by the time the handle exists.
        return False

    def status(self) -> HandleStatus:
        if isinstance(self._exception, CancelledError):
            return HandleStatus.CANCELLED
        if self._exception is not None:
            return HandleStatus.FAILED
        return HandleStatus.COMPLETED

    def result(self, timeout: float | None = None) -> Any:
        if self._exception is not None:
            raise self._exception
        return self._value

    async def result_async(self, timeout: float | None = None) -> Any:
        if self._exception is not None:
            raise self._exception
        return self._value

    def on_progress(self, callback: Callable[[ProgressReport], None]) -> None:
        # Inline execution has already finished; no progress to report.
        pass


class InlineBackend:
    """Execution backend that runs the callable in the current context.

    No thread or process pool is used — the target runs eagerly and
    synchronously in the calling thread.  This is the "no isolation"
    backend suited to tools that are already isolated elsewhere
    (e.g. MCP servers, remote HTTP APIs), where pooling or pickling
    the target would be wrong or impossible.

    Note:
        A *bare* async callable (one without a ``call_sync`` method) is
        driven via ``asyncio.run``, which cannot run while an event loop
        is already active in the calling thread.  Submitting such a
        callable from inside a running loop raises ``RuntimeError`` with
        a clear message — call the coroutine's async path directly
        instead.  Tool wrappers (``BaseToolWrapper``) expose
        ``call_sync``/``call_async`` and are unaffected.
    """

    def submit(
        self,
        fn: Callable[..., Any],
        kwargs: dict[str, Any],
        *,
        execution_id: str | None = None,
        timeout: float | None = None,
    ) -> ExecutionHandle:
        # ``timeout`` is part of the backend interface but has no effect
        # here: inline execution is eager and synchronous, so there is
        # no pending future to time out against.
        exec_id = execution_id or uuid.uuid4().hex

        # Wrap bare async functions so they can run inline.  Tool
        # wrappers (BaseToolWrapper) handle sync/async internally, so
        # only wrap bare async callables passed directly.
        raw_fn = getattr(fn, "fn", fn)
        if asyncio.iscoroutinefunction(raw_fn) and not hasattr(fn, "call_sync"):
            async_fn = fn

            def _sync_wrapper(**kw):  # type: ignore[no-untyped-def]
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    return asyncio.run(async_fn(**kw))
                raise RuntimeError(
                    "InlineBackend cannot run a bare async callable while an "
                    "event loop is already running in this thread. Await the "
                    "coroutine directly (e.g. via the tool's async path) "
                    "instead of submitting it to InlineBackend."
                )

            fn = _sync_wrapper

        # Context injection
        if should_inject_context(fn):
            ctx = ExecutionContext()
            kwargs = {**kwargs, "_ctx": ctx}

        try:
            value = fn(**kwargs)
        except BaseException as exc:  # noqa: BLE001 - captured, re-raised on result()
            return InlineExecutionHandle(exec_id, exception=exc)
        return InlineExecutionHandle(exec_id, value=value)

    def shutdown(self, wait: bool = True) -> None:
        # Nothing to release — inline execution owns no pool.
        pass
