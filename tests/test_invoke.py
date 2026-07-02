"""Tests for ToolRegistry.invoke() — single-tool execution with full pipeline."""

import pytest

from toolregistry import Tool, ToolRegistry
from toolregistry.permissions import PermissionPolicy, PermissionResult, PermissionRule
from toolregistry.tool import ToolMetadata, ToolTag


class TestInvoke:
    def test_basic_invoke(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        reg.register(add)
        result = reg.invoke("add", {"a": 3, "b": 4})
        assert result == 7

    def test_invoke_nonexistent_raises(self):
        reg = ToolRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.invoke("nonexistent", {})

    def test_invoke_disabled_raises(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        reg.register(add)
        reg.disable("add", reason="maintenance")
        with pytest.raises(RuntimeError, match="disabled"):
            reg.invoke("add", {"a": 1, "b": 2})

    def test_invoke_denied_by_permission(self):
        reg = ToolRegistry()

        def dangerous_tool(cmd: str) -> str:
            """Execute a command."""
            return cmd

        tool = Tool.from_function(
            dangerous_tool,
            metadata=ToolMetadata(tags={ToolTag.DESTRUCTIVE}),
        )
        reg.register(tool)

        deny_destructive = PermissionRule(
            name="deny_destructive",
            match=lambda t, p: ToolTag.DESTRUCTIVE in t.metadata.tags,
            result=PermissionResult.DENY,
            reason="Destructive tools blocked",
        )
        reg.set_permission_policy(PermissionPolicy(rules=[deny_destructive]))

        with pytest.raises(PermissionError, match="denied"):
            reg.invoke("dangerous_tool", {"cmd": "rm -rf /"})

    def test_invoke_propagates_tool_error(self):
        reg = ToolRegistry()

        def failing(x: int) -> int:
            raise ValueError("broken")

        reg.register(failing)
        with pytest.raises(ValueError, match="broken"):
            reg.invoke("failing", {"x": 1})

    def test_invoke_logs_success(self):
        reg = ToolRegistry()
        reg.enable_logging()

        def add(a: int, b: int) -> int:
            return a + b

        reg.register(add)
        reg.invoke("add", {"a": 1, "b": 2})

        log = reg.get_execution_log()
        entries = log.get_entries()
        assert len(entries) == 1
        assert entries[0].tool_name == "add"
        assert entries[0].status.value == "success"

    def test_invoke_logs_error(self):
        reg = ToolRegistry()
        reg.enable_logging()

        def failing(x: int) -> int:
            raise ValueError("broken")

        reg.register(failing)
        with pytest.raises(ValueError):
            reg.invoke("failing", {"x": 1})

        log = reg.get_execution_log()
        entries = log.get_entries()
        assert len(entries) == 1
        assert entries[0].status.value == "error"
        assert "broken" in entries[0].error


class TestInvokeWithCodeExecution:
    """Test that CodeExecutionTool uses invoke() for tool calls."""

    @pytest.fixture
    def registry(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        reg.register(add)
        reg.enable_logging()
        return reg

    def test_ptc_tool_call_logged(self, registry):
        """Tool calls via PTC code should appear in execution log."""
        registry.enable_code_execution()
        tool = registry.get_tool("code_execution")
        tool.run({"code": "print(add(a=10, b=20))"})

        log = registry.get_execution_log()
        entries = log.get_entries()
        add_entries = [e for e in entries if e.tool_name == "add"]
        assert len(add_entries) >= 1
        assert add_entries[0].status.value == "success"
