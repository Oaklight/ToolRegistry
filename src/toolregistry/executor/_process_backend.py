"""Process-pool execution backend with cloudpickle serialization."""

from __future__ import annotations

import asyncio
import inspect
import multiprocessing
import os
import pickle
import re
import sys
import threading
import uuid
import warnings
import weakref
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any
from collections.abc import Callable

import cloudpickle

from ._protocol import ExecutionHandle
from ._types import HandleStatus, ProgressReport


class UnpicklableResultError(RuntimeError):
    """A tool result (or its exception) could not cross the worker boundary.

    The process backend returns values by pickling them in the worker and
    unpickling them in the parent.  A value that cannot be pickled never
    reaches the parent's result encoder, so this error explains the
    process-boundary requirement instead of surfacing the bare pickling
    failure (e.g. ``cannot pickle 'generator' object``).
    """


_SENDBACK_FRAME_RE = re.compile(
    r'File "[^"]*concurrent[/\\]futures[/\\]process\.py", line \d+, '
    r"in _sendback_result"
)


_BACKENDS: weakref.WeakSet[ProcessPoolBackend] = weakref.WeakSet()


def _pool_thread_idents() -> set[int]:
    """Return the idents of threads owned by any process-pool backend."""
    idents: set[int] = set()
    for backend in list(_BACKENDS):
        pool = backend._pool
        if pool is None:
            continue
        for attr in (
            "_executor_manager_thread",
            "_queue_management_thread",
            "_shutdown_thread",
        ):
            thread = getattr(pool, attr, None)
            ident = getattr(thread, "ident", None)
            if ident is not None:
                idents.add(ident)
    return idents


def _external_thread_count() -> int:
    """Count threads that are neither the main thread nor pool infrastructure.

    ProcessPoolExecutor keeps a manager thread and queue feeder threads in the
    parent.  They must not make a single-threaded process look threaded, or
    every second pool would switch away from ``fork`` and unguarded scripts
    would break.
    """
    own = _pool_thread_idents()
    return sum(
        1
        for thread in threading.enumerate()
        if thread is not threading.main_thread()
        and thread.ident not in own
        and not thread.name.startswith("QueueFeederThread")
    )


def _pool_context() -> multiprocessing.context.BaseContext:
    """Return a process start context that is safe for the current process.

    The default ``fork`` start method duplicates only the calling thread into
    the child while the parent's other threads keep running, potentially
    holding C-level locks the child inherits.  That is a documented deadlock
    hazard whenever workers are spawned from a threaded process (MCP
    transports, the shared async runtime, integrations), and it also leaks
    stuck children if the parent is interrupted.

    Pick the method that keeps both properties:

    - no external threads: ``fork``.  Nothing else is running, so it is safe,
      and it preserves script/REPL/``stdin`` usage without requiring an
      ``if __name__ == "__main__":`` guard.
    - external threads: ``forkserver`` (``spawn`` where unavailable).  Workers
      start from a clean server process.  Non-fork contexts import
      ``__main__`` in the child, so a file-based entry point needs the
      standard ``if __name__ == "__main__":`` guard.
    - external threads with no importable ``__main__`` (piped script, missing
      file): fall back to ``fork`` with a warning, because the alternative is
      failing outright.  ``python -c`` is unaffected (``__main__`` has no
      ``__file__``).
    """
    methods = multiprocessing.get_all_start_methods()
    if _external_thread_count() == 0 and "fork" in methods:
        return multiprocessing.get_context("fork")

    main = sys.modules.get("__main__")
    main_file = getattr(main, "__file__", None)
    if main_file is not None and not os.path.exists(main_file):
        warnings.warn(
            "The process execution backend cannot import __main__ while "
            "other threads are running; falling back to fork, which may "
            "deadlock if those threads hold locks. Use a file-based entry "
            "point with `if __name__ == '__main__':`, or "
            "execution_mode='thread'.",
            RuntimeWarning,
            stacklevel=2,
        )
        if "fork" in methods:
            return multiprocessing.get_context("fork")
        raise RuntimeError(
            "The process execution backend needs an importable __main__ "
            "module on this platform; use a file-based entry point with "
            "`if __name__ == '__main__':`, or execution_mode='thread'."
        )

    return multiprocessing.get_context(
        "forkserver" if "forkserver" in methods else "spawn"
    )


def _is_worker_pickle_failure(exc: BaseException) -> bool:
    """Return whether *exc* is a worker's failed pickling of its result.

    When a worker cannot serialize its return value,
    ``concurrent.futures`` retries the send with the pickling exception
    itself; the original traceback is attached to the exception it
    delivers to the parent as a ``_RemoteTraceback`` cause.  A tool that
    merely *raises* a similar ``TypeError``/``AttributeError`` has its own
    call frames there instead, so the frame line for
    ``concurrent.futures.process._sendback_result`` distinguishes the two
    without matching on the exception type or message.

    The match is anchored to that frame line rather than the bare
    function name: the remote traceback also contains the tool's own
    exception message, and a message that merely names the function must
    not reclassify the tool's exception as a boundary failure.  Only the
    *first* frame decides: a genuine sendback failure starts at
    ``_sendback_result``, while a tool-raised error starts at
    ``_process_worker``, so even a message that embeds a whole frame line
    stays a tool error.

    Args:
        exc: Exception raised by ``Future.result()`` in the parent.

    Returns:
        ``True`` when the exception came from serializing the result for
        the return trip, ``False`` otherwise.
    """
    cause = exc.__cause__
    if cause is None or type(cause).__name__ != "_RemoteTraceback":
        return False
    for line in str(cause).splitlines():
        stripped = line.strip()
        if stripped.startswith('File "'):
            return _SENDBACK_FRAME_RE.match(stripped) is not None
    return False


def _translate_worker_error(exc: BaseException) -> BaseException:
    """Replace a bare worker pickling failure with an actionable error."""
    if not _is_worker_pickle_failure(exc):
        return exc
    return UnpicklableResultError(
        "the process execution backend must pickle the tool result (or the "
        "tool's exception) to return it from the worker process "
        f"({exc}); return a picklable value, or use the thread backend "
        "(it has no pickling step, but the result must still be "
        "JSON-encodable)"
    )


def _process_worker(
    serialized_fn: bytes,
    kwargs: dict[str, Any],
) -> Any:
    """Deserialize and execute a function in a worker process.

    This is a module-level function so it can be pickled and sent to
    worker processes.

    Args:
        serialized_fn: cloudpickle-serialized callable.
        kwargs: Keyword arguments to pass to the callable.

    Returns:
        The raw function result.  Encoding is the caller's responsibility:
        the parent process runs the value through the tool result encoder
        exactly once, so nothing is stringified here.  The value must
        therefore be picklable to cross the process boundary; a failure to
        do so is reported by the parent as
        :class:`UnpicklableResultError`.
    """
    fn = pickle.loads(serialized_fn)
    return fn(**kwargs)


class ProcessExecutionHandle(ExecutionHandle):
    """Handle wrapping a ProcessPoolExecutor Future.

    Cancellation is hard-cancel: ``future.cancel()`` prevents the task
    from starting. For already-running tasks, cooperative cancellation
    is not supported across processes.
    """

    def __init__(
        self,
        future: Future,
        exec_id: str,
        timeout: float | None,
    ) -> None:
        self._future = future
        self._exec_id = exec_id
        self._timeout = timeout

    @property
    def execution_id(self) -> str:
        return self._exec_id

    def cancel(self) -> bool:
        return self._future.cancel()

    def status(self) -> HandleStatus:
        if self._future.cancelled():
            return HandleStatus.CANCELLED
        if self._future.running():
            return HandleStatus.RUNNING
        if self._future.done():
            exc = self._future.exception(timeout=0)
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
        except Exception as e:
            translated = _translate_worker_error(e)
            if translated is not e:
                raise translated from e
            raise

    async def result_async(self, timeout: float | None = None) -> Any:
        effective_timeout = timeout if timeout is not None else self._timeout
        fut = asyncio.wrap_future(self._future)
        try:
            if effective_timeout is not None:
                return await asyncio.wait_for(fut, effective_timeout)
            return await fut
        except (asyncio.TimeoutError, FuturesTimeoutError) as e:
            raise TimeoutError(str(e)) from e
        except Exception as e:
            translated = _translate_worker_error(e)
            if translated is not e:
                raise translated from e
            raise

    def on_progress(self, callback: Callable[[ProgressReport], None]) -> None:
        # Process backend does not support progress reporting.
        pass


class ProcessPoolBackend:
    """Execution backend using a process pool with cloudpickle serialization.

    Functions are serialized with cloudpickle, sent to worker processes,
    deserialized, and executed. Provides true parallelism but does not
    support cooperative cancellation or progress reporting.
    """

    def __init__(self, max_workers: int | None = None) -> None:
        self._max_workers = max_workers
        # Created on first submit: ProcessPoolExecutor allocates IPC pipes and
        # starts a manager thread at construction, which an idle registry
        # should not hold.
        self._pool: ProcessPoolExecutor | None = None
        self._pool_start_method: str | None = None
        self._external_threads_at_creation = 0
        self._outstanding = 0
        self._thread_growth_warned = False
        _BACKENDS.add(self)

    def _get_pool(self) -> ProcessPoolExecutor:
        """Return the lazily created process pool."""
        if self._pool is None:
            self._external_threads_at_creation = _external_thread_count()
            ctx = _pool_context()
            self._pool = ProcessPoolExecutor(
                max_workers=self._max_workers, mp_context=ctx
            )
            self._pool_start_method = ctx.get_start_method()
        return self._pool

    def _release_slot(self, _future: Future) -> None:
        """Track completion so a pool can be migrated only when idle."""
        self._outstanding -= 1

    def _migrate_if_threaded(self) -> None:
        """Replace a ``fork`` pool once the parent has grown threads.

        The start method is chosen when the pool is created.  A pool created
        while single-threaded stays on ``fork``, so workers spawned later
        would be forked from a threaded parent — the hazard this backend
        exists to avoid.  Recreate the pool when it is idle; if work is in
        flight, warn once rather than discarding it.
        """
        if self._pool is None or self._pool_start_method != "fork":
            return
        if _external_thread_count() <= self._external_threads_at_creation:
            return
        if self._outstanding:
            if not self._thread_growth_warned:
                self._thread_growth_warned = True
                warnings.warn(
                    "The process backend's pool was created with fork and the "
                    "process has since grown threads; workers spawned from "
                    "here may deadlock. Call close() to reset the pool, or "
                    "create the registry after the other threads start.",
                    RuntimeWarning,
                    stacklevel=3,
                )
            return
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._pool = None
        self._pool_start_method = None
        self._external_threads_at_creation = 0
        self._thread_growth_warned = False

    def submit(
        self,
        fn: Callable[..., Any],
        kwargs: dict[str, Any],
        *,
        execution_id: str | None = None,
        timeout: float | None = None,
    ) -> ExecutionHandle:
        exec_id = execution_id or uuid.uuid4().hex

        # A pool created while single-threaded uses fork.  If the process has
        # since grown threads, migrate before adding work so new workers are
        # not forked from a threaded parent.
        self._migrate_if_threaded()

        # Wrap bare async functions so they can run in the worker process.
        # Tool wrappers (BaseToolWrapper) handle sync/async internally,
        # so only wrap bare async callables passed directly.
        raw_fn = getattr(fn, "fn", fn)
        if inspect.iscoroutinefunction(raw_fn) and not hasattr(fn, "call_sync"):
            async_fn = fn

            def _sync_wrapper(**kw):  # type: ignore[no-untyped-def]
                return asyncio.run(async_fn(**kw))

            fn = _sync_wrapper

        # Serialize the callable with cloudpickle
        serialized_fn = cloudpickle.dumps(fn)

        future = self._get_pool().submit(_process_worker, serialized_fn, kwargs)
        self._outstanding += 1
        future.add_done_callback(self._release_slot)
        return ProcessExecutionHandle(future, exec_id, timeout)

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the pool.

        ``wait=False`` abandons queued work and returns immediately;
        ``wait=True`` drains in-flight and queued work.
        """
        if self._pool is None:
            return
        self._pool.shutdown(wait=wait, cancel_futures=not wait)
        self._pool = None
        self._pool_start_method = None
        self._external_threads_at_creation = 0
