"""Backend protocol and execution handle."""

from __future__ import annotations

import abc
from typing import Any, Protocol, runtime_checkable
from collections.abc import Callable

from ._types import HandleStatus, ProgressReport


class ExecutionHandle(abc.ABC):
    """Handle returned by ExecutionBackend.submit().

    Wraps the underlying future/task with cancel, status, result,
    and progress observation capabilities.
    """

    @abc.abstractmethod
    def cancel(self) -> bool:
        """Request cancellation. Returns True if the cancel was accepted."""
        ...

    @abc.abstractmethod
    def status(self) -> HandleStatus:
        """Return the current execution status."""
        ...

    @abc.abstractmethod
    def result(self, timeout: float | None = None) -> Any:
        """Block until the result is available or timeout expires.

        Raises:
            TimeoutError: If timeout expires before completion.
            CancelledError: If the execution was cancelled.
            Exception: If the execution raised an exception.
        """
        ...

    @abc.abstractmethod
    def on_progress(self, callback: Callable[[ProgressReport], None]) -> None:
        """Register a callback for progress updates."""
        ...

    @property
    @abc.abstractmethod
    def execution_id(self) -> str:
        """Unique identifier for this execution."""
        ...


@runtime_checkable
class ExecutionBackend(Protocol):
    """Protocol that all execution backends must satisfy.

    Backends receive a bare ``Callable`` and ``dict`` of arguments.
    They must NOT import any toolregistry types (Tool, ToolCall, etc.).
    """

    def submit(
        self,
        fn: Callable[..., Any],
        kwargs: dict[str, Any],
        *,
        execution_id: str | None = None,
        timeout: float | None = None,
    ) -> ExecutionHandle:
        """Submit a callable for execution.

        Args:
            fn: The callable to execute.
            kwargs: Keyword arguments to pass to fn.
            execution_id: Optional caller-supplied ID. Backend generates
                one if not provided.
            timeout: Per-call timeout in seconds. None means no limit.

        Returns:
            An ExecutionHandle for tracking and controlling the execution.
        """
        ...

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the backend, releasing resources."""
        ...
