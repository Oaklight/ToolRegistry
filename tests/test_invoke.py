"""Tests for ToolRegistry.invoke() and invocation_id tracking."""

import pytest

from toolregistry import Tool, ToolRegistry
from toolregistry.permissions import PermissionPolicy, PermissionResult, PermissionRule
from toolregistry.runtimes import PTC_TOOL_NAME
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


class TestInvocationId:
    def test_auto_generates_sig_id(self):
        reg = ToolRegistry()
        reg.enable_logging()

        def add(a: int, b: int) -> int:
            return a + b

        reg.register(add)
        reg.invoke("add", {"a": 1, "b": 2})

        entries = reg.get_execution_log().get_entries()
        assert len(entries) == 1
        assert entries[0].invocation_id.startswith("tr_sig_")

    def test_custom_invocation_id(self):
        reg = ToolRegistry()
        reg.enable_logging()

        def add(a: int, b: int) -> int:
            return a + b

        reg.register(add)
        reg.invoke("add", {"a": 1, "b": 2}, invocation_id="tr_ptc_test123")

        entries = reg.get_execution_log().get_entries()
        assert entries[0].invocation_id == "tr_ptc_test123"

    def test_filter_by_invocation_id(self):
        reg = ToolRegistry()
        reg.enable_logging()

        def add(a: int, b: int) -> int:
            return a + b

        def mul(a: int, b: int) -> int:
            return a * b

        reg.register(add)
        reg.register(mul)

        reg.invoke("add", {"a": 1, "b": 2}, invocation_id="tr_ptc_aaa")
        reg.invoke("mul", {"a": 3, "b": 4}, invocation_id="tr_ptc_aaa")
        reg.invoke("add", {"a": 5, "b": 6}, invocation_id="tr_sig_bbb")

        log = reg.get_execution_log()
        ptc_entries = log.get_entries(invocation_id="tr_ptc_aaa")
        assert len(ptc_entries) == 2

        sig_entries = log.get_entries(invocation_id="tr_sig_bbb")
        assert len(sig_entries) == 1

    def test_error_logged_with_invocation_id(self):
        reg = ToolRegistry()
        reg.enable_logging()

        def failing(x: int) -> int:
            raise ValueError("broken")

        reg.register(failing)
        with pytest.raises(ValueError):
            reg.invoke("failing", {"x": 1}, invocation_id="tr_sig_err1")

        entries = reg.get_execution_log().get_entries(invocation_id="tr_sig_err1")
        assert len(entries) == 1
        assert entries[0].status.value == "error"


class TestPtcInvocationId:
    """Test that PtcTool generates tr_ptc_ IDs."""

    @pytest.fixture
    def registry(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        reg.register(add)
        reg.enable_logging()
        return reg

    def test_ptc_generates_invocation_id(self, registry):
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)
        tool.run({"code": "print(add(a=1, b=2))"})

        assert registry.ptc.last_invocation_id is not None
        assert registry.ptc.last_invocation_id.startswith("tr_ptc_")

    def test_ptc_tool_calls_share_id(self, registry):
        def mul(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        registry.register(mul)
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)

        tool.run({"code": "s = add(a=1, b=2)\np = mul(a=s, b=3)\nprint(p)"})

        inv_id = registry.ptc.last_invocation_id
        entries = registry.get_execution_log().get_entries(invocation_id=inv_id)
        assert len(entries) == 2
        tool_names = {e.tool_name for e in entries}
        assert tool_names == {"add", "mul"}

    def test_separate_executions_have_different_ids(self, registry):
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)

        tool.run({"code": "print(add(a=1, b=2))"})
        id1 = registry.ptc.last_invocation_id

        tool.run({"code": "print(add(a=3, b=4))"})
        id2 = registry.ptc.last_invocation_id

        assert id1 != id2
