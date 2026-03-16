"""Tests for execution logging infrastructure."""

import threading
import time

import pytest

from toolregistry import ExecutionLog, ExecutionLogEntry, ExecutionStatus


class TestExecutionStatus:
    """Tests for ExecutionStatus enum."""

    def test_status_values(self):
        """Test that status enum has expected values."""
        assert ExecutionStatus.SUCCESS.value == "success"
        assert ExecutionStatus.ERROR.value == "error"
        assert ExecutionStatus.DISABLED.value == "disabled"

    def test_status_is_string_enum(self):
        """Test that status values can be used as strings."""
        assert str(ExecutionStatus.SUCCESS) == "ExecutionStatus.SUCCESS"
        assert ExecutionStatus.SUCCESS == "success"


class TestExecutionLogEntry:
    """Tests for ExecutionLogEntry dataclass."""

    def test_create_entry(self):
        """Test creating an entry with the create factory method."""
        entry = ExecutionLogEntry.create(
            tool_name="calculator.add",
            status=ExecutionStatus.SUCCESS,
            duration_ms=1.5,
            arguments={"a": 1, "b": 2},
            result=3,
        )

        assert entry.tool_name == "calculator.add"
        assert entry.status == ExecutionStatus.SUCCESS
        assert entry.duration_ms == 1.5
        assert entry.arguments == {"a": 1, "b": 2}
        assert entry.result == 3
        assert entry.error is None
        assert entry.metadata == {}
        assert entry.id is not None
        assert entry.timestamp is not None

    def test_create_error_entry(self):
        """Test creating an error entry."""
        entry = ExecutionLogEntry.create(
            tool_name="calculator.divide",
            status=ExecutionStatus.ERROR,
            duration_ms=0.5,
            arguments={"a": 1, "b": 0},
            error="Division by zero",
        )

        assert entry.status == ExecutionStatus.ERROR
        assert entry.error == "Division by zero"
        assert entry.result is None

    def test_create_disabled_entry(self):
        """Test creating a disabled tool entry."""
        entry = ExecutionLogEntry.create(
            tool_name="dangerous_tool",
            status=ExecutionStatus.DISABLED,
            duration_ms=0.0,
            arguments={},
            error="Tool is disabled for security reasons",
        )

        assert entry.status == ExecutionStatus.DISABLED
        assert entry.duration_ms == 0.0

    def test_entry_with_metadata(self):
        """Test creating an entry with metadata."""
        entry = ExecutionLogEntry.create(
            tool_name="api_call",
            status=ExecutionStatus.SUCCESS,
            duration_ms=100.0,
            arguments={"url": "https://api.example.com"},
            result="OK",
            metadata={"request_id": "abc123", "retry_count": 2},
        )

        assert entry.metadata == {"request_id": "abc123", "retry_count": 2}

    def test_entry_is_immutable(self):
        """Test that entry is frozen (immutable)."""
        entry = ExecutionLogEntry.create(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            duration_ms=1.0,
            arguments={},
        )

        with pytest.raises(AttributeError):
            entry.tool_name = "modified"  # type: ignore

    def test_entry_id_is_unique(self):
        """Test that each entry gets a unique ID."""
        entries = [
            ExecutionLogEntry.create(
                tool_name="test",
                status=ExecutionStatus.SUCCESS,
                duration_ms=1.0,
                arguments={},
            )
            for _ in range(100)
        ]

        ids = [e.id for e in entries]
        assert len(ids) == len(set(ids))  # All IDs are unique


class TestExecutionLog:
    """Tests for ExecutionLog class."""

    def test_init_default(self):
        """Test default initialization."""
        log = ExecutionLog()
        assert log.max_entries == 1000
        assert len(log) == 0

    def test_init_custom_max_entries(self):
        """Test initialization with custom max_entries."""
        log = ExecutionLog(max_entries=50)
        assert log.max_entries == 50

    def test_init_invalid_max_entries(self):
        """Test that invalid max_entries raises ValueError."""
        with pytest.raises(ValueError, match="max_entries must be at least 1"):
            ExecutionLog(max_entries=0)

        with pytest.raises(ValueError, match="max_entries must be at least 1"):
            ExecutionLog(max_entries=-1)

    def test_add_entry(self):
        """Test adding entries to the log."""
        log = ExecutionLog()
        entry = ExecutionLogEntry.create(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            duration_ms=1.0,
            arguments={},
        )

        log.add(entry)
        assert len(log) == 1

    def test_ring_buffer_overflow(self):
        """Test that ring buffer correctly handles overflow."""
        log = ExecutionLog(max_entries=5)

        # Add 10 entries
        for i in range(10):
            entry = ExecutionLogEntry.create(
                tool_name=f"tool_{i}",
                status=ExecutionStatus.SUCCESS,
                duration_ms=float(i),
                arguments={"index": i},
            )
            log.add(entry)

        # Should only have 5 entries
        assert len(log) == 5

        # Should have the last 5 entries (tool_5 through tool_9)
        entries = log.get_entries()
        tool_names = [e.tool_name for e in entries]
        assert "tool_9" in tool_names
        assert "tool_5" in tool_names
        assert "tool_0" not in tool_names

    def test_get_entries_no_filter(self):
        """Test getting all entries without filters."""
        log = ExecutionLog()

        for i in range(5):
            entry = ExecutionLogEntry.create(
                tool_name=f"tool_{i}",
                status=ExecutionStatus.SUCCESS,
                duration_ms=float(i),
                arguments={},
            )
            log.add(entry)

        entries = log.get_entries()
        assert len(entries) == 5

    def test_get_entries_with_limit(self):
        """Test getting entries with limit."""
        log = ExecutionLog()

        for i in range(10):
            entry = ExecutionLogEntry.create(
                tool_name=f"tool_{i}",
                status=ExecutionStatus.SUCCESS,
                duration_ms=float(i),
                arguments={},
            )
            log.add(entry)

        entries = log.get_entries(limit=3)
        assert len(entries) == 3

    def test_get_entries_filter_by_tool_name(self):
        """Test filtering entries by tool name."""
        log = ExecutionLog()

        for i in range(5):
            entry = ExecutionLogEntry.create(
                tool_name="calculator.add" if i % 2 == 0 else "calculator.subtract",
                status=ExecutionStatus.SUCCESS,
                duration_ms=float(i),
                arguments={},
            )
            log.add(entry)

        entries = log.get_entries(tool_name="calculator.add")
        assert len(entries) == 3
        assert all(e.tool_name == "calculator.add" for e in entries)

    def test_get_entries_filter_by_status(self):
        """Test filtering entries by status."""
        log = ExecutionLog()

        statuses = [
            ExecutionStatus.SUCCESS,
            ExecutionStatus.ERROR,
            ExecutionStatus.SUCCESS,
            ExecutionStatus.DISABLED,
            ExecutionStatus.SUCCESS,
        ]

        for i, status in enumerate(statuses):
            entry = ExecutionLogEntry.create(
                tool_name=f"tool_{i}",
                status=status,
                duration_ms=float(i),
                arguments={},
            )
            log.add(entry)

        success_entries = log.get_entries(status=ExecutionStatus.SUCCESS)
        assert len(success_entries) == 3

        error_entries = log.get_entries(status=ExecutionStatus.ERROR)
        assert len(error_entries) == 1

    def test_get_entries_filter_by_since(self):
        """Test filtering entries by timestamp."""
        log = ExecutionLog()

        # Add some entries
        for i in range(5):
            entry = ExecutionLogEntry.create(
                tool_name=f"tool_{i}",
                status=ExecutionStatus.SUCCESS,
                duration_ms=float(i),
                arguments={},
            )
            log.add(entry)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # Get entries from the middle
        all_entries = log.get_entries()
        middle_timestamp = all_entries[2].timestamp

        recent_entries = log.get_entries(since=middle_timestamp)
        assert len(recent_entries) >= 1

    def test_get_entries_combined_filters(self):
        """Test combining multiple filters."""
        log = ExecutionLog()

        # Add various entries
        for i in range(10):
            entry = ExecutionLogEntry.create(
                tool_name="calculator.add" if i % 2 == 0 else "calculator.subtract",
                status=ExecutionStatus.SUCCESS if i % 3 != 0 else ExecutionStatus.ERROR,
                duration_ms=float(i),
                arguments={},
            )
            log.add(entry)

        # Filter by both tool_name and status
        entries = log.get_entries(
            tool_name="calculator.add",
            status=ExecutionStatus.SUCCESS,
        )

        assert all(e.tool_name == "calculator.add" for e in entries)
        assert all(e.status == ExecutionStatus.SUCCESS for e in entries)

    def test_get_entries_returns_newest_first(self):
        """Test that entries are returned in reverse chronological order."""
        log = ExecutionLog()

        for i in range(5):
            entry = ExecutionLogEntry.create(
                tool_name=f"tool_{i}",
                status=ExecutionStatus.SUCCESS,
                duration_ms=float(i),
                arguments={},
            )
            log.add(entry)
            time.sleep(0.01)

        entries = log.get_entries()
        timestamps = [e.timestamp for e in entries]

        # Verify descending order
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1]

    def test_clear(self):
        """Test clearing the log."""
        log = ExecutionLog()

        for i in range(5):
            entry = ExecutionLogEntry.create(
                tool_name=f"tool_{i}",
                status=ExecutionStatus.SUCCESS,
                duration_ms=float(i),
                arguments={},
            )
            log.add(entry)

        assert len(log) == 5

        cleared_count = log.clear()
        assert cleared_count == 5
        assert len(log) == 0

    def test_get_stats_empty(self):
        """Test getting stats from empty log."""
        log = ExecutionLog()
        stats = log.get_stats()

        assert stats["total_entries"] == 0
        assert stats["total_added"] == 0
        assert stats["max_entries"] == 1000
        assert stats["by_status"] == {}
        assert stats["by_tool"] == {}
        assert stats["avg_duration_ms"] == 0.0
        assert stats["oldest_entry"] is None
        assert stats["newest_entry"] is None

    def test_get_stats_with_entries(self):
        """Test getting stats with entries."""
        log = ExecutionLog()

        # Add various entries
        entries_data = [
            ("calculator.add", ExecutionStatus.SUCCESS, 10.0),
            ("calculator.add", ExecutionStatus.SUCCESS, 20.0),
            ("calculator.subtract", ExecutionStatus.ERROR, 5.0),
            ("calculator.multiply", ExecutionStatus.SUCCESS, 15.0),
        ]

        for tool_name, status, duration in entries_data:
            entry = ExecutionLogEntry.create(
                tool_name=tool_name,
                status=status,
                duration_ms=duration,
                arguments={},
            )
            log.add(entry)

        stats = log.get_stats()

        assert stats["total_entries"] == 4
        assert stats["total_added"] == 4
        assert stats["by_status"] == {"success": 3, "error": 1}
        assert stats["by_tool"] == {
            "calculator.add": 2,
            "calculator.subtract": 1,
            "calculator.multiply": 1,
        }
        assert stats["avg_duration_ms"] == 12.5  # (10 + 20 + 5 + 15) / 4
        assert stats["oldest_entry"] is not None
        assert stats["newest_entry"] is not None

    def test_get_stats_total_added_after_overflow(self):
        """Test that total_added tracks all entries even after overflow."""
        log = ExecutionLog(max_entries=3)

        for i in range(10):
            entry = ExecutionLogEntry.create(
                tool_name=f"tool_{i}",
                status=ExecutionStatus.SUCCESS,
                duration_ms=float(i),
                arguments={},
            )
            log.add(entry)

        stats = log.get_stats()
        assert stats["total_entries"] == 3  # Only 3 in buffer
        assert stats["total_added"] == 10  # But 10 were added total

    def test_thread_safety_add(self):
        """Test thread safety of add operation."""
        log = ExecutionLog(max_entries=1000)
        num_threads = 10
        entries_per_thread = 100

        def add_entries(thread_id: int):
            for i in range(entries_per_thread):
                entry = ExecutionLogEntry.create(
                    tool_name=f"thread_{thread_id}_tool_{i}",
                    status=ExecutionStatus.SUCCESS,
                    duration_ms=float(i),
                    arguments={"thread": thread_id, "index": i},
                )
                log.add(entry)

        threads = [
            threading.Thread(target=add_entries, args=(i,)) for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All entries should be added
        assert len(log) == num_threads * entries_per_thread

    def test_thread_safety_concurrent_operations(self):
        """Test thread safety with concurrent add, get, and clear operations."""
        log = ExecutionLog(max_entries=100)
        stop_event = threading.Event()
        errors: list[Exception] = []

        def add_entries():
            try:
                while not stop_event.is_set():
                    entry = ExecutionLogEntry.create(
                        tool_name="test",
                        status=ExecutionStatus.SUCCESS,
                        duration_ms=1.0,
                        arguments={},
                    )
                    log.add(entry)
            except Exception as e:
                errors.append(e)

        def read_entries():
            try:
                while not stop_event.is_set():
                    _ = log.get_entries()
                    _ = log.get_stats()
            except Exception as e:
                errors.append(e)

        def clear_entries():
            try:
                while not stop_event.is_set():
                    log.clear()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_entries),
            threading.Thread(target=add_entries),
            threading.Thread(target=read_entries),
            threading.Thread(target=read_entries),
            threading.Thread(target=clear_entries),
        ]

        for t in threads:
            t.start()

        # Let threads run for a short time
        time.sleep(0.5)
        stop_event.set()

        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0


class TestToolRegistryLoggingIntegration:
    """Tests for ToolRegistry logging integration."""

    def test_enable_logging(self):
        """Test enabling logging on ToolRegistry."""
        from toolregistry import ToolRegistry

        registry = ToolRegistry()
        log = registry.enable_logging(max_entries=500)

        assert log is not None
        assert log.max_entries == 500
        assert registry.get_execution_log() is log

    def test_disable_logging(self):
        """Test disabling logging on ToolRegistry."""
        from toolregistry import ToolRegistry

        registry = ToolRegistry()
        registry.enable_logging()
        registry.disable_logging()

        assert registry.get_execution_log() is None

    def test_get_execution_log_when_not_enabled(self):
        """Test getting execution log when not enabled."""
        from toolregistry import ToolRegistry

        registry = ToolRegistry()
        assert registry.get_execution_log() is None

    def test_logging_disabled_tool_execution(self):
        """Test that disabled tool executions are logged."""
        from toolregistry import ToolRegistry

        registry = ToolRegistry()
        log = registry.enable_logging()

        def my_tool(x: int) -> int:
            """A simple tool."""
            return x * 2

        registry.register(my_tool)
        registry.disable("my_tool", reason="Under maintenance")

        # Create a mock tool call
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "my_tool", "arguments": '{"x": 5}'},
            }
        ]

        registry.execute_tool_calls(tool_calls)

        entries = log.get_entries()
        assert len(entries) == 1
        assert entries[0].status == ExecutionStatus.DISABLED
        assert entries[0].tool_name == "my_tool"
        assert "Under maintenance" in (entries[0].error or "")
