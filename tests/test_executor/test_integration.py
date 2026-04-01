"""Integration tests for executor backends with ToolRegistry."""

import json
import time

import pytest

from toolregistry import Tool, ToolMetadata, ToolRegistry
from toolregistry.executor import ExecutionContext


def _sync_add(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


async def _async_multiply(x: int, y: int) -> int:
    """Multiply two numbers."""
    return x * y


def _make_tool_call(name: str, args: dict, call_id: str = "call_1"):
    """Create an OpenAI-style tool call dict."""
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


class TestExecuteToolCallsThread:
    def test_basic_execution(self):
        reg = ToolRegistry()
        reg.register(_sync_add)
        tc = _make_tool_call("_sync_add", {"x": 3, "y": 4})
        result = reg.execute_tool_calls([tc], execution_mode="thread")
        assert result["call_1"] == "7"

    def test_async_tool(self):
        reg = ToolRegistry()
        reg.register(_async_multiply)
        tc = _make_tool_call("_async_multiply", {"x": 3, "y": 5})
        result = reg.execute_tool_calls([tc], execution_mode="thread")
        assert result["call_1"] == "15"


class TestExecuteToolCallsProcess:
    def test_basic_execution(self):
        reg = ToolRegistry()
        reg.register(_sync_add)
        tc = _make_tool_call("_sync_add", {"x": 10, "y": 20})
        result = reg.execute_tool_calls([tc], execution_mode="process")
        assert result["call_1"] == "30"


class TestDisabledToolsRegression:
    def test_disabled_tool_returns_error(self):
        reg = ToolRegistry()
        reg.register(_sync_add)
        reg.disable("_sync_add", reason="maintenance")
        tc = _make_tool_call("_sync_add", {"x": 1, "y": 2})
        result = reg.execute_tool_calls([tc])
        assert "disabled" in result["call_1"].lower()


class TestExecutionLoggingRegression:
    def test_logging_records_entries(self):
        reg = ToolRegistry()
        reg.register(_sync_add)
        log = reg.enable_logging()
        tc = _make_tool_call("_sync_add", {"x": 1, "y": 2}, call_id="log_1")
        reg.execute_tool_calls([tc], execution_mode="thread")
        entries = log.get_entries()
        assert len(entries) == 1
        assert entries[0].tool_name == "_sync_add"


class TestTimeout:
    def test_timeout_enforcement(self):
        def slow_func(x: int) -> int:
            """Slow function."""
            time.sleep(10)
            return x

        reg = ToolRegistry()
        reg.register(Tool.from_function(slow_func, metadata=ToolMetadata(timeout=0.1)))
        tc = _make_tool_call("slow_func", {"x": 1}, call_id="timeout_1")
        result = reg.execute_tool_calls([tc], execution_mode="thread")
        assert "timed out" in result["timeout_1"].lower()


class TestConcurrencySafe:
    def test_unsafe_tools_run_sequentially(self):
        """Tools with is_concurrency_safe=False should not be batched."""
        call_order = []

        def tool_a(x: int) -> int:
            """Tool A."""
            call_order.append(("a_start", time.monotonic()))
            time.sleep(0.05)
            call_order.append(("a_end", time.monotonic()))
            return x

        def tool_b(x: int) -> int:
            """Tool B."""
            call_order.append(("b_start", time.monotonic()))
            time.sleep(0.05)
            call_order.append(("b_end", time.monotonic()))
            return x

        reg = ToolRegistry()
        reg.register(
            Tool.from_function(tool_a, metadata=ToolMetadata(is_concurrency_safe=False))
        )
        reg.register(
            Tool.from_function(tool_b, metadata=ToolMetadata(is_concurrency_safe=False))
        )

        tc_a = _make_tool_call("tool_a", {"x": 1}, call_id="a")
        tc_b = _make_tool_call("tool_b", {"x": 2}, call_id="b")
        result = reg.execute_tool_calls([tc_a, tc_b], execution_mode="thread")

        assert result["a"] == "1"
        assert result["b"] == "2"

        # Verify sequential: a_end should happen before b_start
        events = {name: ts for name, ts in call_order}
        assert events["a_end"] <= events["b_start"]


class TestSetExecutionMode:
    def test_switch_mode(self):
        reg = ToolRegistry()
        reg.set_default_execution_mode("thread")
        reg.register(_sync_add)
        tc = _make_tool_call("_sync_add", {"x": 1, "y": 1})
        result = reg.execute_tool_calls([tc])
        assert result["call_1"] == "2"

    def test_invalid_mode_raises(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError):
            reg.set_default_execution_mode("invalid")  # type: ignore[arg-type]


class TestContextInjection:
    def test_ctx_injected_in_thread_mode(self):
        def tool_with_ctx(x: int, _ctx: ExecutionContext) -> str:
            """Tool that uses context."""
            return f"x={x}, has_ctx={_ctx is not None}"

        reg = ToolRegistry()
        reg.register(tool_with_ctx)
        tc = _make_tool_call("tool_with_ctx", {"x": 42})
        result = reg.execute_tool_calls([tc], execution_mode="thread")
        assert "has_ctx=True" in result["call_1"]
