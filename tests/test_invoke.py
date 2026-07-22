"""Tests for ToolRegistry.invoke() and invocation_id tracking.

invoke() returns a structured Result — ``ToolCallResult`` on success,
``ErrorResult`` on any failure (including access control) — and never
raises for those conditions.
"""

from toolregistry import Tool, ToolRegistry
from toolregistry.llm.tool_calls import ErrorResult, ToolCallResult
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
        assert isinstance(result, ToolCallResult)
        assert result.name == "add"
        assert result.result == "7"

    def test_invoke_nonexistent_returns_error(self):
        reg = ToolRegistry()
        result = reg.invoke("nonexistent", {})
        assert isinstance(result, ErrorResult)
        assert "not registered" in result.message

    def test_invoke_disabled_returns_error(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        reg.register(add)
        reg.disable("add", reason="maintenance")
        result = reg.invoke("add", {"a": 1, "b": 2})
        assert isinstance(result, ErrorResult)
        assert "disabled" in result.message

    def test_invoke_denied_by_permission_returns_error(self):
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

        result = reg.invoke("dangerous_tool", {"cmd": "rm -rf /"})
        assert isinstance(result, ErrorResult)
        assert "denied" in result.message

    def test_invoke_tool_error_returns_error(self):
        reg = ToolRegistry()

        def failing(x: int) -> int:
            raise ValueError("broken")

        reg.register(failing)
        result = reg.invoke("failing", {"x": 1})
        assert isinstance(result, ErrorResult)
        assert "broken" in result.message

    def test_invoke_result_id_matches_invocation_id(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        reg.register(add)
        result = reg.invoke("add", {"a": 1, "b": 2}, invocation_id="tr_sig_fixed")
        assert result.id == "tr_sig_fixed"


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
        result = reg.invoke("failing", {"x": 1}, invocation_id="tr_sig_err1")
        assert isinstance(result, ErrorResult)

        entries = reg.get_execution_log().get_entries(invocation_id="tr_sig_err1")
        assert len(entries) == 1
        assert entries[0].status.value == "error"
