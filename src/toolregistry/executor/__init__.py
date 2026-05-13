"""Pluggable execution backend package.

This package has ZERO imports from toolregistry internals.
It operates exclusively on ``Callable + dict`` arguments.
"""

from ._process_backend import ProcessPoolBackend
from ._protocol import ExecutionBackend, ExecutionHandle
from ._thread_backend import ThreadBackend
from ._types import (
    CancelledError,
    ExecutionContext,
    HandleStatus,
    ProgressReport,
)

__all__ = [
    # Types
    "CancelledError",
    "ExecutionContext",
    "HandleStatus",
    "ProgressReport",
    # Protocol + ABC
    "ExecutionBackend",
    "ExecutionHandle",
    # Backends
    "ProcessPoolBackend",
    "ThreadBackend",
]
