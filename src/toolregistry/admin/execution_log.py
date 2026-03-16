"""Execution logging infrastructure for ToolRegistry.

This module provides data structures and utilities for logging tool executions,
including a thread-safe ring buffer implementation for efficient storage.
"""

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    """Status of a tool execution."""

    SUCCESS = "success"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ExecutionLogEntry:
    """Single execution log entry.

    This immutable dataclass represents a single tool execution record,
    capturing all relevant information about the execution.

    Attributes:
        id: Unique identifier (UUID) for this log entry.
        tool_name: Name of the executed tool.
        timestamp: When the execution occurred.
        status: Execution status (success, error, or disabled).
        duration_ms: Execution duration in milliseconds.
        arguments: Input arguments passed to the tool.
        result: Execution result (only for successful executions).
        error: Error message (only for failed executions).
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

    def __init__(self, max_entries: int = 1000) -> None:
        """Initialize with maximum entries limit.

        Args:
            max_entries: Maximum number of log entries to retain.
                When this limit is exceeded, oldest entries are removed.
                Defaults to 1000.

        Raises:
            ValueError: If max_entries is less than 1.
        """
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._entries: deque[ExecutionLogEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._total_added: int = 0

    @property
    def max_entries(self) -> int:
        """Return the maximum number of entries this log can hold."""
        return self._max_entries

    def add(self, entry: ExecutionLogEntry) -> None:
        """Add a new log entry (thread-safe).

        If the log is at capacity, the oldest entry is automatically
        removed to make room for the new entry.

        Args:
            entry: The execution log entry to add.
        """
        with self._lock:
            self._entries.append(entry)
            self._total_added += 1

    def get_entries(
        self,
        limit: int | None = None,
        tool_name: str | None = None,
        status: ExecutionStatus | None = None,
        since: datetime | None = None,
    ) -> list[ExecutionLogEntry]:
        """Query log entries with optional filters.

        Returns entries in reverse chronological order (newest first).

        Args:
            limit: Maximum number of entries to return. If None, returns all
                matching entries.
            tool_name: Filter by tool name. If None, matches all tools.
            status: Filter by execution status. If None, matches all statuses.
            since: Filter entries after this timestamp. If None, no time filter.

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
