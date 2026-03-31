"""Execution value types — zero toolregistry imports."""

from __future__ import annotations

import enum
import threading
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable


class ExecutionStatus(str, enum.Enum):
    """Lifecycle status of a single execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressReport:
    """Progress update emitted by a running tool function.

    Attributes:
        fraction: 0.0-1.0, or None if indeterminate.
        message: Human-readable description of current step.
        detail: Arbitrary payload for structured progress data.
    """

    fraction: float | None = None
    message: str = ""
    detail: Any = None


class ExecutionContext:
    """Cooperative cancellation and progress reporting handle.

    Tool functions that wish to participate in cancellation/progress
    should declare a parameter named ``_ctx: ExecutionContext`` in
    their signature. The backend will auto-inject it.
    """

    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._progress_callbacks: list[Callable[[ProgressReport], None]] = []

    @property
    def cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_event.is_set()

    def check_cancelled(self) -> None:
        """Raise ``CancelledError`` if cancellation was requested.

        Cooperative tool functions should call this periodically.
        """
        if self._cancel_event.is_set():
            raise CancelledError("Execution was cancelled")

    def report_progress(
        self,
        fraction: float | None = None,
        message: str = "",
        detail: Any = None,
    ) -> None:
        """Emit a progress report to all registered listeners."""
        report = ProgressReport(fraction=fraction, message=message, detail=detail)
        for cb in self._progress_callbacks:
            cb(report)

    # -- Internal API used by backends --

    def _request_cancel(self) -> None:
        """Signal cancellation (called by backend/handle)."""
        self._cancel_event.set()

    def _add_progress_listener(self, cb: Callable[[ProgressReport], None]) -> None:
        """Register a progress callback (called by handle)."""
        self._progress_callbacks.append(cb)


class CancelledError(Exception):
    """Raised when a cooperatively-cancellable execution is cancelled."""
