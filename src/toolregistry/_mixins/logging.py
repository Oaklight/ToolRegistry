"""Execution logging mixin for ToolRegistry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..admin import ExecutionLog


class ExecutionLoggingMixin:
    """Mixin providing execution logging capabilities."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._execution_log: ExecutionLog | None = None

    def enable_logging(
        self, max_entries: int = 1000, *, full_record: bool = False
    ) -> ExecutionLog:
        """Enable execution logging with a ring buffer.

        Creates an ExecutionLog instance that records tool execution details
        including timing, arguments, results, and errors.

        By default the log is safe to expose: known credential keys
        (``password``, ``token``, ``authorization``, ...) are masked,
        arguments and results longer than 2000 JSON characters are replaced
        by a preview, and tracebacks are dropped while ``exception_type``
        and ``error`` are kept.  Pass ``full_record=True`` to keep the raw
        payloads and tracebacks; only do that when the log is not reachable
        by untrusted callers.

        Args:
            max_entries: Maximum number of log entries to retain.
                When this limit is exceeded, oldest entries are removed.
                Defaults to 1000.
            full_record: Store arguments, results and tracebacks verbatim.
                Defaults to False.

        Returns:
            The ExecutionLog instance for querying logged executions.

        Example:
            ```python
            registry = ToolRegistry()
            log = registry.enable_logging(max_entries=500)
            # ... execute tools ...
            stats = log.get_stats()
            ```
        """
        from ..admin import ExecutionLog

        self._execution_log = ExecutionLog(
            max_entries=max_entries, full_record=full_record
        )
        return self._execution_log

    def disable_logging(self) -> None:
        """Disable execution logging.

        Clears the execution log and stops recording new executions.
        Any existing log entries are discarded.

        Example:
            ```python
            registry.disable_logging()
            ```
        """
        self._execution_log = None

    def get_execution_log(self) -> ExecutionLog | None:
        """Get the current execution log instance.

        Returns:
            The ExecutionLog instance if logging is enabled, None otherwise.

        Example:
            ```python
            log = registry.get_execution_log()
            if log:
                entries = log.get_entries(limit=10)
            ```
        """
        return self._execution_log
