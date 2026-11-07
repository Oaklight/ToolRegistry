"""Execution logging infrastructure for ToolRegistry.

This module provides data structures and utilities for logging tool executions,
including a thread-safe ring buffer implementation for efficient storage.
"""

import json
import logging
import threading
import uuid
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    """Status of a tool execution."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    DISABLED = "disabled"


#: Replacement used for a value whose key names a credential.
_REDACTED = "***REDACTED***"

#: Longest JSON encoding kept for ``arguments`` or ``result`` before the
#: payload is replaced by a bounded preview.
DEFAULT_MAX_FIELD_CHARS = 2000

#: Largest nesting depth a logged value is walked.  Deeper values are
#: replaced instead of traversed, which also bounds work on cyclic input.
_MAX_REDACT_DEPTH = 8

#: Exact normalised key names that always carry a credential.
_SENSITIVE_KEY_NAMES = frozenset(
    {
        "access_key",
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "client_secret",
        "cookie",
        "credential",
        "credentials",
        "id_token",
        "passwd",
        "password",
        "private_key",
        "pwd",
        "refresh_token",
        "secret",
        "secret_key",
        "session",
        "session_id",
        "session_token",
        "set_cookie",
        "token",
        "x_api_key",
    }
)

#: Suffixes that mark a compound key as credential-bearing.  ``_key`` alone
#: is omitted on purpose: an ordinary mapping argument often uses it.
_SENSITIVE_KEY_SUFFIXES = (
    "_access_key",
    "_access_token",
    "_api_key",
    "_apikey",
    "_authorization",
    "_client_secret",
    "_credential",
    "_credentials",
    "_passwd",
    "_password",
    "_private_key",
    "_pwd",
    "_refresh_token",
    "_secret",
    "_secret_key",
    "_session",
    "_session_id",
    "_session_token",
    "_token",
)


def _is_sensitive_key(key: object) -> bool:
    """Return whether *key* names a credential that must not be logged.

    Args:
        key: A mapping key, which is normalised before matching.

    Returns:
        True when the key matches a known credential name or suffix.
    """
    normalized = str(key).strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in _SENSITIVE_KEY_NAMES or normalized.endswith(
        _SENSITIVE_KEY_SUFFIXES
    )


def _redact(value: Any, *, depth: int = 0, seen: set[int] | None = None) -> Any:
    """Return a copy of *value* with credential-bearing keys masked.

    Traversal is depth-limited and cycle-safe.  Containers keep their shape;
    only values under a sensitive key are replaced.

    Args:
        value: The value to copy.
        depth: Current recursion depth.
        seen: Ids of containers already visited on this branch.

    Returns:
        A redacted copy, or a marker for an over-deep or cyclic value.
    """
    if depth > _MAX_REDACT_DEPTH:
        return "<max-depth>"
    if isinstance(value, dict):
        if seen is None:
            seen = set()
        if id(value) in seen:
            return "<cycle>"
        seen = seen | {id(value)}
        return {
            key: (
                _REDACTED
                if _is_sensitive_key(key)
                else _redact(item, depth=depth + 1, seen=seen)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        if seen is None:
            seen = set()
        if id(value) in seen:
            return "<cycle>"
        seen = seen | {id(value)}
        return [_redact(item, depth=depth + 1, seen=seen) for item in value]
    return value


def _bounded_payload(value: Any, max_chars: int) -> Any:
    """Redact *value*, then bound its JSON encoding to *max_chars*.

    A value that already fits is returned as the redacted structure, so the
    panel keeps rendering JSON.  A larger value becomes a small marker with a
    truncated preview, which caps both the memory kept per entry and the
    response size.

    Args:
        value: The argument mapping or result to sanitise.
        max_chars: Maximum JSON length to keep.

    Returns:
        The redacted value, or a preview marker when it is too large.
    """
    redacted = _redact(value)
    try:
        encoded = json.dumps(redacted, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return {"truncated": True, "preview": "<unserializable>"}
    if len(encoded) <= max_chars:
        return redacted
    return {
        "truncated": True,
        "size": len(encoded),
        "preview": encoded[:max_chars],
    }


def _bounded_text(text: str | None, max_chars: int) -> str | None:
    """Truncate *text* to *max_chars*, marking the cut."""
    if text is None or len(text) <= max_chars:
        return text
    return text[:max_chars] + "...<truncated>"


def _sanitize_entry(entry: "ExecutionLogEntry", max_chars: int) -> "ExecutionLogEntry":
    """Return *entry* with payloads redacted, bounded, and traceback dropped.

    The exception type and message stay: together they describe the failure
    without the local paths and library versions a full traceback exposes.

    Args:
        entry: The entry to sanitise.
        max_chars: Maximum JSON length kept for arguments and result.

    Returns:
        A sanitised copy of *entry*.
    """
    return replace(
        entry,
        arguments=_bounded_payload(entry.arguments, max_chars),
        result=_bounded_payload(entry.result, max_chars),
        error=_bounded_text(entry.error, max_chars),
        traceback=None,
    )


@dataclass(frozen=True)
class ExecutionLogEntry:
    """Single execution log entry.

    This immutable dataclass represents a single tool execution record,
    capturing all relevant information about the execution.

    Attributes:
        id: Unique identifier (UUID) for this log entry.
        tool_name: Name of the executed tool.
        timestamp: When the execution occurred.
        status: Execution status (success, error, timeout, or disabled).
        duration_ms: Execution duration in milliseconds.
        arguments: Input arguments passed to the tool.
        result: Execution result (only for successful executions).
        error: Error message (only for failed executions).
        exception_type: Qualified name of the exception class (e.g. "ValueError").
        traceback: Formatted traceback string from the exception.
        metadata: Additional metadata about the execution.
    """

    id: str
    tool_name: str
    timestamp: datetime
    status: ExecutionStatus
    duration_ms: float
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None
    exception_type: str | None = None
    traceback: str | None = None
    invocation_id: str | None = None
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        tool_name: str,
        status: ExecutionStatus,
        duration_ms: float,
        arguments: dict[str, Any],
        result: Any = None,
        error: str | None = None,
        exception_type: str | None = None,
        traceback: str | None = None,
        invocation_id: str | None = None,
        warnings: tuple[str, ...] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ExecutionLogEntry":
        """Create a new ExecutionLogEntry with auto-generated id and timestamp.

        Args:
            tool_name: Name of the executed tool.
            status: Execution status.
            duration_ms: Execution duration in milliseconds.
            arguments: Input arguments passed to the tool.
            result: Execution result (for successful executions).
            error: Error message (for failed executions).
            exception_type: Qualified name of the exception class.
            traceback: Formatted traceback string.
            invocation_id: Groups related tool calls. Prefixes:
                ``tr_bat_`` (batch), ``tr_ptc_`` (PTC),
                ``tr_sig_`` (single invoke).
            warnings: Warning messages captured during execution.
            metadata: Additional metadata.

        Returns:
            A new ExecutionLogEntry instance.
        """
        return cls(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            timestamp=datetime.now(),
            status=status,
            duration_ms=duration_ms,
            arguments=arguments,
            result=result,
            error=error,
            exception_type=exception_type,
            traceback=traceback,
            invocation_id=invocation_id,
            warnings=warnings or (),
            metadata=metadata or {},
        )


class ExecutionLog:
    """Thread-safe execution log with ring buffer storage.

    This class provides a fixed-size, thread-safe log for storing tool
    execution records. When the maximum capacity is reached, oldest
    entries are automatically removed to make room for new ones.

    Attributes:
        max_entries: Maximum number of entries to store.

    Example:
        >>> log = ExecutionLog(max_entries=100)
        >>> entry = ExecutionLogEntry.create(
        ...     tool_name="calculator.add",
        ...     status=ExecutionStatus.SUCCESS,
        ...     duration_ms=1.5,
        ...     arguments={"a": 1, "b": 2},
        ...     result=3,
        ... )
        >>> log.add(entry)
        >>> len(log)
        1
    """

    def __init__(
        self,
        max_entries: int = 1000,
        *,
        full_record: bool = False,
        max_field_chars: int = DEFAULT_MAX_FIELD_CHARS,
    ) -> None:
        """Initialize with maximum entries limit.

        Args:
            max_entries: Maximum number of log entries to retain.
                When this limit is exceeded, oldest entries are removed.
                Defaults to 1000.
            full_record: Store arguments, results and tracebacks verbatim.
                Defaults to False, which masks credential-bearing keys,
                replaces payloads larger than *max_field_chars* with a
                preview, and drops the traceback in favour of
                ``exception_type`` and ``error``.  Enable this only when the
                log is not reachable by untrusted callers.
            max_field_chars: Maximum JSON length kept for ``arguments`` and
                ``result`` when *full_record* is False.  Defaults to
                :data:`DEFAULT_MAX_FIELD_CHARS`.

        Raises:
            ValueError: If max_entries or max_field_chars is less than 1.
        """
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        if max_field_chars < 1:
            raise ValueError("max_field_chars must be at least 1")
        self._max_entries = max_entries
        self._full_record = full_record
        self._max_field_chars = max_field_chars
        self._entries: deque[ExecutionLogEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._total_added: int = 0

    @property
    def max_entries(self) -> int:
        """Return the maximum number of entries this log can hold."""
        return self._max_entries

    @property
    def full_record(self) -> bool:
        """Return whether entries keep unredacted payloads and tracebacks."""
        return self._full_record

    @property
    def max_field_chars(self) -> int:
        """Return the maximum JSON length kept per payload by default."""
        return self._max_field_chars

    def add(self, entry: ExecutionLogEntry) -> None:
        """Add a new log entry (thread-safe).

        If the log is at capacity, the oldest entry is automatically
        removed to make room for the new entry.  Unless the log was opened
        with ``full_record=True``, the entry is sanitised first: known
        credential keys are masked, oversized payloads are replaced by a
        preview, and the traceback is dropped.

        Args:
            entry: The execution log entry to add.
        """
        with self._lock:
            if not self._full_record:
                entry = _sanitize_entry(entry, self._max_field_chars)
            self._entries.append(entry)
            self._total_added += 1

    def get_entries(
        self,
        limit: int | None = None,
        tool_name: str | None = None,
        status: ExecutionStatus | None = None,
        since: datetime | None = None,
        invocation_id: str | None = None,
        has_warnings: bool | None = None,
    ) -> list[ExecutionLogEntry]:
        """Query log entries with optional filters.

        Returns entries in reverse chronological order (newest first).

        Args:
            limit: Maximum number of entries to return. If None, returns all
                matching entries.
            tool_name: Filter by tool name. If None, matches all tools.
            status: Filter by execution status. If None, matches all statuses.
            since: Filter entries after this timestamp. If None, no time filter.
            invocation_id: Filter by invocation ID. Use this to retrieve
                all tool calls from a single batch (``tr_bat_``), PTC
                execution (``tr_ptc_``), or standalone invoke (``tr_sig_``).
            has_warnings: If ``True``, return only entries with warnings;
                if ``False``, only entries without warnings.  ``None``
                disables the filter.

        Returns:
            List of matching ExecutionLogEntry objects, newest first.
        """
        with self._lock:
            # Create a copy to avoid holding lock during filtering
            entries = list(self._entries)

        # Apply filters
        filtered = entries
        if tool_name is not None:
            filtered = [e for e in filtered if e.tool_name == tool_name]
        if status is not None:
            filtered = [e for e in filtered if e.status == status]
        if since is not None:
            filtered = [e for e in filtered if e.timestamp >= since]
        if invocation_id is not None:
            filtered = [e for e in filtered if e.invocation_id == invocation_id]
        if has_warnings is not None:
            if has_warnings:
                filtered = [e for e in filtered if e.warnings]
            else:
                filtered = [e for e in filtered if not e.warnings]

        # Sort by timestamp descending (newest first)
        filtered.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply limit
        if limit is not None:
            filtered = filtered[:limit]

        return filtered

    def clear(self) -> int:
        """Clear all entries, return count of cleared entries.

        Returns:
            Number of entries that were cleared.
        """
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            return count

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics.

        Returns a dictionary containing aggregate statistics about
        the logged executions.

        Returns:
            Dictionary with the following keys:
                - total_entries: Current number of entries in the log.
                - total_added: Total number of entries ever added.
                - max_entries: Maximum capacity of the log.
                - by_status: Count of entries by status.
                - by_tool: Count of entries by tool name.
                - avg_duration_ms: Average execution duration in milliseconds.
                - oldest_entry: Timestamp of the oldest entry (or None).
                - newest_entry: Timestamp of the newest entry (or None).
        """
        with self._lock:
            entries = list(self._entries)
            total_added = self._total_added

        # Calculate statistics
        by_status: dict[str, int] = {}
        by_tool: dict[str, int] = {}
        total_duration = 0.0

        for entry in entries:
            # Count by status
            status_key = entry.status.value
            by_status[status_key] = by_status.get(status_key, 0) + 1

            # Count by tool
            by_tool[entry.tool_name] = by_tool.get(entry.tool_name, 0) + 1

            # Sum duration
            total_duration += entry.duration_ms

        # Calculate average duration
        avg_duration = total_duration / len(entries) if entries else 0.0

        # Get oldest and newest timestamps
        oldest = min((e.timestamp for e in entries), default=None)
        newest = max((e.timestamp for e in entries), default=None)

        return {
            "total_entries": len(entries),
            "total_added": total_added,
            "max_entries": self._max_entries,
            "by_status": by_status,
            "by_tool": by_tool,
            "avg_duration_ms": avg_duration,
            "oldest_entry": oldest,
            "newest_entry": newest,
        }

    def __len__(self) -> int:
        """Return current number of entries."""
        with self._lock:
            return len(self._entries)


class _WarningHandler(logging.Handler):
    """Lightweight handler that accumulates WARNING+ messages."""

    __slots__ = ("messages",)

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.messages.append(self.format(record))
        except Exception:
            pass  # never break the caller


@contextmanager
def warning_collector(
    logger_name: str | None = None,
) -> Generator[_WarningHandler, None, None]:
    """Context manager that captures WARNING-level log records.

    Attaches a temporary :class:`_WarningHandler` to the specified
    logger (or the root logger when *logger_name* is ``None``) for the
    duration of the ``with`` block.  The handler is always removed on
    exit, even if the block raises.

    The captured messages are available via ``handler.messages``.

    Example::

        with warning_collector("toolregistry") as wc:
            some_tool_call()
        print(wc.messages)  # ["Unhandled content block type: ..."]
    """
    target = logging.getLogger(logger_name)
    handler = _WarningHandler()
    target.addHandler(handler)
    try:
        yield handler
    finally:
        target.removeHandler(handler)
