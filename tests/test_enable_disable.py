"""Tests for Tool enable/disable functionality (Phase 3)."""

import json

from toolregistry.tool_registry import ToolRegistry
from toolregistry.types import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Subtract b from a."""
    return a - b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


class MathTools:
    @staticmethod
    def square(x: int) -> int:
        """Square a number."""
        return x * x

    @staticmethod
    def double(x: int) -> int:
        """Double a number."""
        return x * 2

    @staticmethod
    def negate(x: int) -> int:
        """Negate a number."""
        return -x


# ===========================================================================
# 1. Basic disable/enable
# ===========================================================================


class TestBasicDisableEnable:
    """Verify basic disable and enable operations on individual tools."""

    def test_tool_enabled_by_default(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        assert registry.is_enabled("add") is True

    def test_disable_tool(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.disable("add")
        assert registry.is_enabled("add") is False

    def test_enable_after_disable(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.disable("add")
        assert registry.is_enabled("add") is False
        registry.enable("add")
        assert registry.is_enabled("add") is True

    def test_disable_with_reason(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.disable("add", reason="under maintenance")
        assert registry.get_disable_reason("add") == "under maintenance"

    def test_enable_clears_reason(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.disable("add", reason="under maintenance")
        registry.enable("add")
        assert registry.get_disable_reason("add") is None


# ===========================================================================
# 2. Namespace-level disable
# ===========================================================================


class TestNamespaceDisable:
    """Verify disabling/enabling at the namespace level."""

    def test_disable_namespace_disables_all_tools(self):
        registry = ToolRegistry(name="test")
        registry.register_from_class(MathTools, with_namespace=True)
        tools = registry.list_all_tools()
        assert len(tools) == 3

        registry.disable("math_tools")
        for tool_name in tools:
            assert registry.is_enabled(tool_name) is False

    def test_disable_namespace_reason_propagates(self):
        registry = ToolRegistry(name="test")
        registry.register_from_class(MathTools, with_namespace=True)
        tools = registry.list_all_tools()

        registry.disable("math_tools", reason="namespace disabled")
        for tool_name in tools:
            assert registry.get_disable_reason(tool_name) == "namespace disabled"

    def test_enable_namespace_enables_all_tools(self):
        registry = ToolRegistry(name="test")
        registry.register_from_class(MathTools, with_namespace=True)
        tools = registry.list_all_tools()

        registry.disable("math_tools")
        for tool_name in tools:
            assert registry.is_enabled(tool_name) is False

        registry.enable("math_tools")
        for tool_name in tools:
            assert registry.is_enabled(tool_name) is True


# ===========================================================================
# 3. Method-level overrides namespace-level
# ===========================================================================


class TestMethodOverridesNamespace:
    """Verify that method-level disable reason takes priority over namespace-level."""

    def test_method_reason_overrides_namespace_reason(self):
        registry = ToolRegistry(name="test")
        registry.register_from_class(MathTools, with_namespace=True)
        tools = registry.list_all_tools()

        # Disable namespace
        registry.disable("math_tools", reason="namespace disabled")

        # Also disable a specific tool with a different reason
        specific_tool = tools[0]
        registry.disable(specific_tool, reason="method disabled")

        # Method-level reason takes priority
        assert registry.get_disable_reason(specific_tool) == "method disabled"

        # Other tools in namespace still get namespace reason
        for tool_name in tools[1:]:
            assert registry.get_disable_reason(tool_name) == "namespace disabled"

    def test_both_method_and_namespace_disabled(self):
        registry = ToolRegistry(name="test")
        registry.register_from_class(MathTools, with_namespace=True)
        tools = registry.list_all_tools()

        specific_tool = tools[0]
        registry.disable("math_tools", reason="namespace disabled")
        registry.disable(specific_tool, reason="method disabled")

        # All tools should be disabled
        for tool_name in tools:
            assert registry.is_enabled(tool_name) is False


# ===========================================================================
# 4. list_tools vs list_all_tools
# ===========================================================================


class TestListToolsFiltering:
    """Verify that list_tools only returns enabled tools."""

    def test_list_tools_excludes_disabled(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.register(subtract)
        registry.register(multiply)

        registry.disable("subtract")

        enabled = registry.list_tools()
        assert "add" in enabled
        assert "subtract" not in enabled
        assert "multiply" in enabled

    def test_list_all_tools_includes_disabled(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.register(subtract)
        registry.register(multiply)

        registry.disable("subtract")

        all_tools = registry.list_all_tools()
        assert "add" in all_tools
        assert "subtract" in all_tools
        assert "multiply" in all_tools

    def test_get_available_tools_matches_list_tools(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.register(subtract)

        registry.disable("subtract")

        assert registry.get_available_tools() == registry.list_tools()

    def test_list_tools_empty_when_all_disabled(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.register(subtract)

        registry.disable("add")
        registry.disable("subtract")

        assert registry.list_tools() == []
        assert len(registry.list_all_tools()) == 2


# ===========================================================================
# 5. get_tools_json filtering
# ===========================================================================


class TestGetToolsJsonFiltering:
    """Verify that get_tools_json filters disabled tools."""

    def test_get_tools_json_excludes_disabled(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.register(subtract)
        registry.register(multiply)

        registry.disable("subtract")

        schemas = registry.get_tools_json()
        schema_names = [
            s["function"]["name"]
            for s in schemas
            if "function" in s and "name" in s["function"]
        ]
        assert "add" in schema_names
        assert "subtract" not in schema_names
        assert "multiply" in schema_names

    def test_get_tools_json_specific_tool_returns_even_if_disabled(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.register(subtract)

        registry.disable("subtract")

        # Querying a specific tool by name should still return its schema
        schemas = registry.get_tools_json(tool_name="subtract")
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "subtract"

    def test_get_tools_json_all_disabled(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.register(subtract)

        registry.disable("add")
        registry.disable("subtract")

        schemas = registry.get_tools_json()
        assert schemas == []


# ===========================================================================
# 6. execute_tool_calls with disabled tools
# ===========================================================================


class TestExecuteToolCallsDisabled:
    """Verify that execute_tool_calls rejects disabled tools."""

    def _make_tool_call(self, name: str, arguments: dict, call_id: str = "call_1"):
        """Create a ChatCompletionMessageFunctionToolCall for testing."""
        return ChatCompletionMessageFunctionToolCall(
            id=call_id,
            function=Function(
                name=name,
                arguments=json.dumps(arguments),
            ),
        )

    def test_execute_enabled_tool(self):
        registry = ToolRegistry(name="test")
        registry.register(add)

        tool_call = self._make_tool_call("add", {"a": 3, "b": 4})
        results = registry.execute_tool_calls([tool_call])
        assert str(results["call_1"]) == "7"

    def test_execute_disabled_tool_returns_error(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.disable("add", reason="under maintenance")

        tool_call = self._make_tool_call("add", {"a": 3, "b": 4})
        results = registry.execute_tool_calls([tool_call])
        assert "call_1" in results
        assert "disabled" in results["call_1"].lower()
        assert "under maintenance" in results["call_1"]

    def test_execute_mixed_enabled_disabled(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.register(subtract)

        registry.disable("subtract", reason="deprecated")

        tc_add = self._make_tool_call("add", {"a": 1, "b": 2}, call_id="call_add")
        tc_sub = self._make_tool_call("subtract", {"a": 5, "b": 3}, call_id="call_sub")
        results = registry.execute_tool_calls([tc_add, tc_sub])

        assert str(results["call_add"]) == "3"
        assert "disabled" in results["call_sub"].lower()
        assert "deprecated" in results["call_sub"]

    def test_execute_disabled_tool_default_reason(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.disable("add")

        tool_call = self._make_tool_call("add", {"a": 1, "b": 2})
        results = registry.execute_tool_calls([tool_call])
        assert "disabled" in results["call_1"].lower()


# ===========================================================================
# 7. Edge cases
# ===========================================================================


class TestEdgeCases:
    """Verify edge cases for enable/disable operations."""

    def test_disable_nonexistent_name_no_error(self):
        registry = ToolRegistry(name="test")
        # Should not raise
        registry.disable("nonexistent_tool")

    def test_enable_non_disabled_name_no_error(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        # Should not raise
        registry.enable("add")

    def test_is_enabled_nonexistent_tool_returns_true(self):
        registry = ToolRegistry(name="test")
        # Non-existent tool is not in _disabled, so returns True
        assert registry.is_enabled("nonexistent_tool") is True

    def test_get_disable_reason_nonexistent_tool_returns_none(self):
        registry = ToolRegistry(name="test")
        assert registry.get_disable_reason("nonexistent_tool") is None

    def test_disable_with_empty_reason(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.disable("add", reason="")
        assert registry.is_enabled("add") is False
        assert registry.get_disable_reason("add") == ""

    def test_disable_same_tool_twice_updates_reason(self):
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.disable("add", reason="first reason")
        registry.disable("add", reason="second reason")
        assert registry.get_disable_reason("add") == "second reason"

    def test_enable_nonexistent_name_no_error(self):
        registry = ToolRegistry(name="test")
        # Should not raise even if name was never disabled
        registry.enable("never_disabled")


# ===========================================================================
# 8. get_tools_status
# ===========================================================================


class TestGetToolsStatus:
    """Verify get_tools_status returns correct status information for all tools."""

    def test_empty_registry_returns_empty_list(self):
        """Test that an empty registry returns an empty list."""
        registry = ToolRegistry(name="test")
        status = registry.get_tools_status()
        assert status == []

    def test_single_enabled_tool(self):
        """Test status of a single enabled tool."""
        registry = ToolRegistry(name="test")
        registry.register(add)

        status = registry.get_tools_status()
        assert len(status) == 1
        assert status[0]["name"] == "add"
        assert status[0]["enabled"] is True
        assert status[0]["reason"] is None
        assert status[0]["namespace"] is None

    def test_single_disabled_tool_with_reason(self):
        """Test status of a single disabled tool with a reason."""
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.disable("add", reason="Under maintenance")

        status = registry.get_tools_status()
        assert len(status) == 1
        assert status[0]["name"] == "add"
        assert status[0]["enabled"] is False
        assert status[0]["reason"] == "Under maintenance"
        assert status[0]["namespace"] is None

    def test_mixed_enabled_disabled_tools(self):
        """Test status with a mix of enabled and disabled tools."""
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.register(subtract)
        registry.register(multiply)

        registry.disable("subtract", reason="Deprecated")

        status = registry.get_tools_status()
        assert len(status) == 3

        # Convert to dict for easier lookup
        status_dict = {s["name"]: s for s in status}

        assert status_dict["add"]["enabled"] is True
        assert status_dict["add"]["reason"] is None

        assert status_dict["subtract"]["enabled"] is False
        assert status_dict["subtract"]["reason"] == "Deprecated"

        assert status_dict["multiply"]["enabled"] is True
        assert status_dict["multiply"]["reason"] is None

    def test_namespace_tools_status(self):
        """Test status of tools registered with a namespace."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(MathTools, with_namespace=True)

        status = registry.get_tools_status()
        assert len(status) == 3

        for tool_status in status:
            assert tool_status["enabled"] is True
            assert tool_status["reason"] is None
            assert tool_status["namespace"] == "math_tools"
            # Tool names use "-" as separator (e.g., "math_tools-square")
            assert tool_status["name"].startswith("math_tools-")

    def test_namespace_disabled_tools_status(self):
        """Test status when namespace is disabled."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(MathTools, with_namespace=True)
        registry.disable("math_tools", reason="Namespace disabled")

        status = registry.get_tools_status()
        assert len(status) == 3

        for tool_status in status:
            assert tool_status["enabled"] is False
            assert tool_status["reason"] == "Namespace disabled"
            assert tool_status["namespace"] == "math_tools"

    def test_method_level_override_in_status(self):
        """Test that method-level disable reason appears in status."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(MathTools, with_namespace=True)

        # Disable namespace
        registry.disable("math_tools", reason="Namespace disabled")

        # Override one specific tool (using "-" separator)
        registry.disable("math_tools-square", reason="Method disabled")

        status = registry.get_tools_status()
        status_dict = {s["name"]: s for s in status}

        # Method-level reason takes priority
        assert status_dict["math_tools-square"]["reason"] == "Method disabled"

        # Other tools get namespace reason
        assert status_dict["math_tools-double"]["reason"] == "Namespace disabled"
        assert status_dict["math_tools-negate"]["reason"] == "Namespace disabled"

    def test_disabled_tool_without_reason(self):
        """Test status of a disabled tool without a reason."""
        registry = ToolRegistry(name="test")
        registry.register(add)
        registry.disable("add")

        status = registry.get_tools_status()
        assert len(status) == 1
        assert status[0]["enabled"] is False
        # Empty string reason is still returned
        assert status[0]["reason"] == ""
