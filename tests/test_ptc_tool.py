"""Tests for the PtcTool (PTC meta-tool)."""

import pytest

from toolregistry import ToolRegistry
from toolregistry.runtimes import PTC_TOOL_NAME, PtcTool


@pytest.fixture
def registry():
    """Registry with a couple of tools registered."""
    reg = ToolRegistry()

    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def multiply(a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    reg.register(add)
    reg.register(multiply)
    return reg


class TestPtcTool:
    def test_basic_execution(self, registry):
        executor = PtcTool(registry)
        result = executor.execute("print(1 + 2)")
        assert result.strip() == "3"

    def test_math_import(self, registry):
        executor = PtcTool(registry)
        result = executor.execute("import math; print(math.pi)")
        assert "3.14" in result

    def test_error_returns_stderr(self, registry):
        executor = PtcTool(registry)
        result = executor.execute("1 / 0")
        assert "Error:" in result
        assert "ZeroDivisionError" in result

    def test_dangerous_code_rejected(self, registry):
        executor = PtcTool(registry)
        with pytest.raises(ValueError, match="Import not allowed"):
            executor.execute("import os; os.system('ls')")

    def test_call_tool_in_namespace(self, registry):
        """Tools are directly callable in the code namespace."""
        executor = PtcTool(registry)
        result = executor.execute("print(add(a=3, b=4))")
        assert result.strip() == "7"

    def test_call_multiple_tools(self, registry):
        """Multi-tool orchestration in a single code block."""
        executor = PtcTool(registry)
        code = (
            "s = add(a=10, b=20)\n"
            "p = multiply(a=s, b=3)\n"
            "print(f'sum={s}, product={p}')"
        )
        result = executor.execute(code)
        assert "sum=30" in result
        assert "product=90" in result

    def test_namespace_excludes_self(self, registry):
        """code_execution tool should not be in its own namespace."""
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)
        result = tool.run({"code": f"print('{PTC_TOOL_NAME}' in dir())"})
        assert result.strip() == "False"

    def test_tool_doc_accessible(self, registry):
        """Tool docstring accessible via __doc__ (for help())."""
        executor = PtcTool(registry)
        result = executor.execute("print(add.__doc__)")
        assert "Add two numbers" in result

    def test_multiline_computation(self, registry):
        executor = PtcTool(registry)
        code = (
            "results = []\n"
            "for i in range(5):\n"
            "    results.append(add(a=i, b=i*10))\n"
            "print(results)"
        )
        result = executor.execute(code)
        assert "[0, 11, 22, 33, 44]" in result

    def test_syntax_error_rejected(self, registry):
        executor = PtcTool(registry)
        with pytest.raises(SyntaxError):
            executor.execute("def")


class TestRegistryIntegration:
    def test_enable_ptc(self, registry):
        registry.ptc.enable()
        assert PTC_TOOL_NAME in registry
        assert registry.ptc.enabled

    def test_enable_twice_raises(self, registry):
        registry.ptc.enable()
        with pytest.raises(ValueError, match="already enabled"):
            registry.ptc.enable()

    def test_re_enable_after_disable(self, registry):
        registry.ptc.enable(timeout=10)
        registry.ptc.disable()
        registry.ptc.enable(timeout=60)  # should work
        assert registry.ptc.enabled

    def test_disable_ptc_tool(self, registry):
        registry.ptc.enable()
        assert PTC_TOOL_NAME in registry
        registry.ptc.disable()
        assert PTC_TOOL_NAME not in registry

    def test_disable_noop_when_not_enabled(self, registry):
        registry.ptc.disable()  # should not raise

    def test_last_invocation_id_preserved_after_disable(self, registry):
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)
        tool.run({"code": "print(add(a=1, b=2))"})
        inv_id = registry.ptc.last_invocation_id
        assert inv_id is not None

        registry.ptc.disable()
        assert registry.ptc.last_invocation_id == inv_id

    def test_ptc_tool_tool_schema(self, registry):
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)
        assert tool is not None
        assert "code" in tool.parameters.get("properties", {})

    def test_execute_via_registry(self, registry):
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)
        result = tool.run({"code": "print(42)"})
        assert "42" in result

    def test_execute_tool_call_via_registry(self, registry):
        """Full end-to-end: LLM tool call → code execution → tool invocation."""
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)
        result = tool.run({"code": "print(add(a=100, b=200))"})
        assert "300" in result
