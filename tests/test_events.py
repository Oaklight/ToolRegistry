"""Tests for the callback mechanism in ToolRegistry.

This module tests the on_change() and remove_on_change() callback mechanism,
including ChangeEvent data class, callback registration/removal, event emission,
exception isolation, and thread safety.
"""

import threading
import time

import pytest

from toolregistry import ChangeCallback, ChangeEvent, ChangeEventType, ToolRegistry


# ============== ChangeEvent Tests ==============


class TestChangeEvent:
    """Tests for the ChangeEvent data class."""

    def test_change_event_creation(self):
        """Test basic ChangeEvent creation."""
        event = ChangeEvent(
            event_type=ChangeEventType.REGISTER,
            tool_name="my_tool",
        )
        assert event.event_type == ChangeEventType.REGISTER
        assert event.tool_name == "my_tool"
        assert event.reason is None
        assert event.metadata == {}

    def test_change_event_with_reason(self):
        """Test ChangeEvent with reason field."""
        event = ChangeEvent(
            event_type=ChangeEventType.DISABLE,
            tool_name="my_tool",
            reason="Maintenance",
        )
        assert event.event_type == ChangeEventType.DISABLE
        assert event.tool_name == "my_tool"
        assert event.reason == "Maintenance"

    def test_change_event_with_metadata(self):
        """Test ChangeEvent with metadata field."""
        metadata = {"source": "config", "version": 1}
        event = ChangeEvent(
            event_type=ChangeEventType.REFRESH_ALL,
            metadata=metadata,
        )
        assert event.event_type == ChangeEventType.REFRESH_ALL
        assert event.tool_name is None
        assert event.metadata == metadata

    def test_change_event_is_immutable(self):
        """Test that ChangeEvent is immutable (frozen dataclass)."""
        event = ChangeEvent(
            event_type=ChangeEventType.REGISTER,
            tool_name="my_tool",
        )
        with pytest.raises(AttributeError):
            event.tool_name = "other_tool"  # type: ignore

    def test_change_event_type_values(self):
        """Test all ChangeEventType enum values."""
        assert ChangeEventType.REGISTER.value == "register"
        assert ChangeEventType.UNREGISTER.value == "unregister"
        assert ChangeEventType.ENABLE.value == "enable"
        assert ChangeEventType.DISABLE.value == "disable"
        assert ChangeEventType.REFRESH.value == "refresh"
        assert ChangeEventType.REFRESH_ALL.value == "refresh_all"


# ============== Callback Registration Tests ==============


class TestOnChange:
    """Tests for on_change() callback registration."""

    def test_callback_registration(self):
        """Test basic callback registration."""
        registry = ToolRegistry()
        events: list[ChangeEvent] = []
        registry.on_change(events.append)

        def sample_tool():
            """A sample tool."""
            return "result"

        registry.register(sample_tool)

        assert len(events) == 1
        assert events[0].event_type == ChangeEventType.REGISTER
        assert events[0].tool_name == "sample_tool"

    def test_multiple_callbacks(self):
        """Test multiple callbacks are all invoked."""
        registry = ToolRegistry()
        events1: list[ChangeEvent] = []
        events2: list[ChangeEvent] = []

        registry.on_change(events1.append)
        registry.on_change(events2.append)

        def sample_tool():
            """A sample tool."""
            return "result"

        registry.register(sample_tool)

        assert len(events1) == 1
        assert len(events2) == 1
        assert events1[0] == events2[0]

    def test_duplicate_callback_registration(self):
        """Test that the same callback can be registered multiple times."""
        registry = ToolRegistry()
        events: list[ChangeEvent] = []

        registry.on_change(events.append)
        registry.on_change(events.append)  # Register same callback again

        def sample_tool():
            """A sample tool."""
            return "result"

        registry.register(sample_tool)

        # Callback should be invoked twice
        assert len(events) == 2
        assert events[0] == events[1]

    def test_callbacks_invoked_in_order(self):
        """Test that callbacks are invoked in registration order."""
        registry = ToolRegistry()
        order: list[int] = []

        registry.on_change(lambda e: order.append(1))
        registry.on_change(lambda e: order.append(2))
        registry.on_change(lambda e: order.append(3))

        def sample_tool():
            """A sample tool."""
            return "result"

        registry.register(sample_tool)

        assert order == [1, 2, 3]


# ============== Callback Removal Tests ==============


class TestRemoveOnChange:
    """Tests for remove_on_change() callback removal."""

    def test_remove_callback(self):
        """Test basic callback removal."""
        registry = ToolRegistry()
        events: list[ChangeEvent] = []
        callback = events.append

        registry.on_change(callback)
        result = registry.remove_on_change(callback)

        assert result is True

        def sample_tool():
            """A sample tool."""
            return "result"

        registry.register(sample_tool)

        # Callback should not be invoked
        assert len(events) == 0

    def test_remove_nonexistent_callback(self):
        """Test removing a callback that was not registered."""
        registry = ToolRegistry()

        def some_callback(event: ChangeEvent) -> None:
            pass

        result = registry.remove_on_change(some_callback)
        assert result is False

    def test_remove_first_occurrence_only(self):
        """Test that remove_on_change only removes the first occurrence."""
        registry = ToolRegistry()
        events: list[ChangeEvent] = []
        callback = events.append

        registry.on_change(callback)
        registry.on_change(callback)  # Register twice

        result = registry.remove_on_change(callback)
        assert result is True

        def sample_tool():
            """A sample tool."""
            return "result"

        registry.register(sample_tool)

        # Callback should still be invoked once (second registration remains)
        assert len(events) == 1


# ============== Event Emission Tests ==============


class TestEventEmission:
    """Tests for event emission on various operations."""

    def test_register_emits_event(self):
        """Test that register() emits a REGISTER event."""
        registry = ToolRegistry()
        events: list[ChangeEvent] = []
        registry.on_change(events.append)

        def my_tool():
            """A tool."""
            return "result"

        registry.register(my_tool)

        assert len(events) == 1
        assert events[0].event_type == ChangeEventType.REGISTER
        assert events[0].tool_name == "my_tool"

    def test_disable_emits_event(self):
        """Test that disable() emits a DISABLE event."""
        registry = ToolRegistry()

        def my_tool():
            """A tool."""
            return "result"

        registry.register(my_tool)

        events: list[ChangeEvent] = []
        registry.on_change(events.append)

        registry.disable("my_tool", reason="Testing")

        assert len(events) == 1
        assert events[0].event_type == ChangeEventType.DISABLE
        assert events[0].tool_name == "my_tool"
        assert events[0].reason == "Testing"

    def test_disable_without_reason(self):
        """Test that disable() with empty reason sets reason to None."""
        registry = ToolRegistry()

        def my_tool():
            """A tool."""
            return "result"

        registry.register(my_tool)

        events: list[ChangeEvent] = []
        registry.on_change(events.append)

        registry.disable("my_tool")

        assert len(events) == 1
        assert events[0].event_type == ChangeEventType.DISABLE
        assert events[0].reason is None

    def test_enable_emits_event(self):
        """Test that enable() emits an ENABLE event."""
        registry = ToolRegistry()

        def my_tool():
            """A tool."""
            return "result"

        registry.register(my_tool)
        registry.disable("my_tool")

        events: list[ChangeEvent] = []
        registry.on_change(events.append)

        registry.enable("my_tool")

        assert len(events) == 1
        assert events[0].event_type == ChangeEventType.ENABLE
        assert events[0].tool_name == "my_tool"


# ============== Exception Isolation Tests ==============


class TestExceptionIsolation:
    """Tests for exception isolation in callbacks."""

    def test_callback_exception_does_not_propagate(self):
        """Test that exceptions in callbacks do not propagate."""
        registry = ToolRegistry()

        def bad_callback(event: ChangeEvent) -> None:
            raise RuntimeError("Test error")

        registry.on_change(bad_callback)

        def sample_tool():
            """A sample tool."""
            return "result"

        # Should not raise
        registry.register(sample_tool)

    def test_callback_exception_does_not_affect_other_callbacks(self):
        """Test that one callback's exception doesn't affect others."""
        registry = ToolRegistry()
        events: list[ChangeEvent] = []

        def bad_callback(event: ChangeEvent) -> None:
            raise RuntimeError("Test error")

        def good_callback(event: ChangeEvent) -> None:
            events.append(event)

        registry.on_change(bad_callback)
        registry.on_change(good_callback)

        def sample_tool():
            """A sample tool."""
            return "result"

        registry.register(sample_tool)

        # Good callback should still run
        assert len(events) == 1

    def test_multiple_bad_callbacks(self):
        """Test that multiple bad callbacks don't break the chain."""
        registry = ToolRegistry()
        events: list[ChangeEvent] = []

        def bad_callback1(event: ChangeEvent) -> None:
            raise RuntimeError("Error 1")

        def bad_callback2(event: ChangeEvent) -> None:
            raise ValueError("Error 2")

        def good_callback(event: ChangeEvent) -> None:
            events.append(event)

        registry.on_change(bad_callback1)
        registry.on_change(good_callback)
        registry.on_change(bad_callback2)

        def sample_tool():
            """A sample tool."""
            return "result"

        registry.register(sample_tool)

        # Good callback should still run
        assert len(events) == 1


# ============== Thread Safety Tests ==============


class TestThreadSafety:
    """Tests for thread safety of the callback mechanism."""

    def test_concurrent_callback_registration(self):
        """Test concurrent callback registration is thread-safe."""
        registry = ToolRegistry()
        callbacks_added = []

        def add_callback():
            def cb(e: ChangeEvent) -> None:
                pass

            registry.on_change(cb)
            callbacks_added.append(cb)

        threads = [threading.Thread(target=add_callback) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(callbacks_added) == 100

    def test_concurrent_callback_removal(self):
        """Test concurrent callback removal is thread-safe."""
        registry = ToolRegistry()
        callbacks = []

        # Register 100 callbacks
        for _ in range(100):

            def cb(e: ChangeEvent) -> None:
                pass

            registry.on_change(cb)
            callbacks.append(cb)

        results: list[bool] = []

        def remove_callback(cb: ChangeCallback):
            result = registry.remove_on_change(cb)
            results.append(result)

        threads = [
            threading.Thread(target=remove_callback, args=(cb,)) for cb in callbacks
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All removals should succeed
        assert all(results)
        assert len(results) == 100

    def test_concurrent_registration_and_callback_modification(self):
        """Test concurrent tool registration and callback modification."""
        registry = ToolRegistry()
        results: list[str] = []
        lock = threading.Lock()

        def callback(event: ChangeEvent) -> None:
            with lock:
                results.append(event.tool_name or "")
            time.sleep(0.001)  # Simulate slow callback

        registry.on_change(callback)

        def register_tools():
            for i in range(10):

                def tool():
                    """A tool."""
                    return "result"

                tool.__name__ = f"tool_{i}"
                registry.register(tool, name=f"tool_{i}")

        def modify_callbacks():
            for _ in range(5):

                def new_cb(e: ChangeEvent) -> None:
                    pass

                registry.on_change(new_cb)
                time.sleep(0.002)
                registry.remove_on_change(new_cb)

        t1 = threading.Thread(target=register_tools)
        t2 = threading.Thread(target=modify_callbacks)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # All 10 tools should have triggered the callback
        assert len(results) == 10

    def test_callback_can_modify_registry(self):
        """Test that callbacks can safely modify the registry."""
        registry = ToolRegistry()
        disabled_tools: list[str] = []

        def auto_disable_callback(event: ChangeEvent) -> None:
            if event.event_type == ChangeEventType.REGISTER:
                if event.tool_name and event.tool_name.startswith("auto_disable_"):
                    registry.disable(event.tool_name, reason="Auto-disabled")
                    disabled_tools.append(event.tool_name)

        registry.on_change(auto_disable_callback)

        def auto_disable_tool():
            """A tool that should be auto-disabled."""
            return "result"

        def normal_tool():
            """A normal tool."""
            return "result"

        registry.register(auto_disable_tool)
        registry.register(normal_tool)

        assert "auto_disable_tool" in disabled_tools
        assert not registry.is_enabled("auto_disable_tool")
        assert registry.is_enabled("normal_tool")

    def test_callback_can_remove_itself(self):
        """Test that a callback can safely remove itself during iteration."""
        registry = ToolRegistry()
        call_count = 0

        def self_removing_callback(event: ChangeEvent) -> None:
            nonlocal call_count
            call_count += 1
            registry.remove_on_change(self_removing_callback)

        registry.on_change(self_removing_callback)

        def tool1():
            """Tool 1."""
            return "result"

        def tool2():
            """Tool 2."""
            return "result"

        registry.register(tool1)
        registry.register(tool2)

        # Callback should only be called once (for tool1)
        # because it removes itself after the first call
        assert call_count == 1


# ============== Integration Tests ==============


class TestIntegration:
    """Integration tests for the callback mechanism."""

    def test_full_lifecycle(self):
        """Test a full tool lifecycle with callbacks."""
        registry = ToolRegistry()
        events: list[ChangeEvent] = []
        registry.on_change(events.append)

        def my_tool():
            """A tool."""
            return "result"

        # Register
        registry.register(my_tool)
        assert len(events) == 1
        assert events[-1].event_type == ChangeEventType.REGISTER

        # Disable
        registry.disable("my_tool", reason="Maintenance")
        assert len(events) == 2
        assert events[-1].event_type == ChangeEventType.DISABLE
        assert events[-1].reason == "Maintenance"

        # Enable
        registry.enable("my_tool")
        assert len(events) == 3
        assert events[-1].event_type == ChangeEventType.ENABLE

    def test_namespace_tool_registration(self):
        """Test callback with namespaced tool registration."""
        registry = ToolRegistry()
        events: list[ChangeEvent] = []
        registry.on_change(events.append)

        def my_tool():
            """A tool."""
            return "result"

        registry.register(my_tool, namespace="my_namespace")

        assert len(events) == 1
        assert events[0].event_type == ChangeEventType.REGISTER
        # Note: namespace separator is '-' not '.'
        assert events[0].tool_name == "my_namespace-my_tool"
