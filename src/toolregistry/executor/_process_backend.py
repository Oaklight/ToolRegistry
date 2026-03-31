"""Process-pool execution backend with cloudpickle serialization."""

from __future__ import annotations

import asyncio
import json
import pickle
import uuid
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any
from collections.abc import Callable

import cloudpickle

from ._helpers import make_sync_wrapper
from ._protocol import ExecutionHandle
from ._types import ExecutionStatus, ProgressReport


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
        The function result (JSON-serializable or stringified).
    """
    fn = pickle.loads(serialized_fn)
    result = fn(**kwargs)
    # Ensure JSON-serializable result
    try:
        json.dumps(result)
    except (TypeError, ValueError):
        result = str(result)
    return result


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

    def status(self) -> ExecutionStatus:
        if self._future.cancelled():
            return ExecutionStatus.CANCELLED
        if self._future.running():
            return ExecutionStatus.RUNNING
        if self._future.done():
            exc = self._future.exception(timeout=0)
            if exc is not None:
                return ExecutionStatus.FAILED
            return ExecutionStatus.COMPLETED
        return ExecutionStatus.PENDING

    def result(self, timeout: float | None = None) -> Any:
        effective_timeout = timeout if timeout is not None else self._timeout
        try:
            return self._future.result(timeout=effective_timeout)
        except FuturesTimeoutError as e:
            raise TimeoutError(str(e)) from e

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

        # Auto-wrap async functions
        if asyncio.iscoroutinefunction(fn):
            fn = make_sync_wrapper(fn)

        # Serialize the callable with cloudpickle
        serialized_fn = cloudpickle.dumps(fn)

        future = self._pool.submit(_process_worker, serialized_fn, kwargs)
        return ProcessExecutionHandle(future, exec_id, timeout)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
