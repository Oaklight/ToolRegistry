"""Process-pool execution backend with cloudpickle serialization."""

from __future__ import annotations

import asyncio
import pickle
import uuid
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


def _is_worker_pickle_failure(exc: BaseException) -> bool:
    """Return whether *exc* is a worker's failed pickling of its result.

    When a worker cannot serialize its return value,
    ``concurrent.futures`` retries the send with the pickling exception
    itself; the original traceback is attached to the exception it
    delivers to the parent as a ``_RemoteTraceback`` cause.  A tool that
    merely *raises* a similar ``TypeError``/``AttributeError`` has its own
    call frames there instead, so the ``_sendback_result`` frame
    distinguishes the two without matching on the exception type or
    message.

    Args:
        exc: Exception raised by ``Future.result()`` in the parent.

    Returns:
        ``True`` when the exception came from serializing the result for
        the return trip, ``False`` otherwise.
    """
    cause = exc.__cause__
    if cause is None or type(cause).__name__ != "_RemoteTraceback":
        return False
    return "_sendback_result" in str(cause)


def _translate_worker_error(exc: BaseException) -> BaseException:
    """Replace a bare worker pickling failure with an actionable error."""
    if not _is_worker_pickle_failure(exc):
        return exc
    return UnpicklableResultError(
        "the process execution backend must pickle the tool result (or the "
        "tool's exception) to return it from the worker process "
        f"({exc}); return a picklable value or use the thread backend"
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
        self._pool = ProcessPoolExecutor(max_workers=max_workers)

    def submit(
        self,
        fn: Callable[..., Any],
        kwargs: dict[str, Any],
        *,
        execution_id: str | None = None,
        timeout: float | None = None,
    ) -> ExecutionHandle:
        exec_id = execution_id or uuid.uuid4().hex

        # Wrap bare async functions so they can run in the worker process.
        # Tool wrappers (BaseToolWrapper) handle sync/async internally,
        # so only wrap bare async callables passed directly.
        raw_fn = getattr(fn, "fn", fn)
        if asyncio.iscoroutinefunction(raw_fn) and not hasattr(fn, "call_sync"):
            async_fn = fn

            def _sync_wrapper(**kw):  # type: ignore[no-untyped-def]
                return asyncio.run(async_fn(**kw))

            fn = _sync_wrapper

        # Serialize the callable with cloudpickle
        serialized_fn = cloudpickle.dumps(fn)

        future = self._pool.submit(_process_worker, serialized_fn, kwargs)
        return ProcessExecutionHandle(future, exec_id, timeout)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
