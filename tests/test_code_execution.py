"""Tests for the CodeExecutionTool (PTC meta-tool)."""

import pytest

from toolregistry import ToolRegistry
from toolregistry.runtimes import CODE_EXECUTION_NAME, CodeExecutionTool


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


class TestCodeExecutionTool:
    def test_basic_execution(self, registry):
        executor = CodeExecutionTool(registry)
        result = executor.execute("print(1 + 2)")
        assert result.strip() == "3"

    def test_math_import(self, registry):
        executor = CodeExecutionTool(registry)
        result = executor.execute("import math; print(math.pi)")
        assert "3.14" in result

    def test_error_returns_stderr(self, registry):
        executor = CodeExecutionTool(registry)
        result = executor.execute("1 / 0")
        assert "Error:" in result
        assert "ZeroDivisionError" in result

    def test_dangerous_code_rejected(self, registry):
        executor = CodeExecutionTool(registry)
        with pytest.raises(ValueError, match="Import not allowed"):
            executor.execute("import os; os.system('ls')")

    def test_call_tool_in_namespace(self, registry):
        """Tools are directly callable in the code namespace."""
        executor = CodeExecutionTool(registry)
        result = executor.execute("print(add(a=3, b=4))")
        assert result.strip() == "7"

    def test_call_multiple_tools(self, registry):
        """Multi-tool orchestration in a single code block."""
        executor = CodeExecutionTool(registry)
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
        registry.enable_code_execution()
        executor = registry._code_execution
        result = executor.execute(f"print('{CODE_EXECUTION_NAME}' in dir())")
        assert result.strip() == "False"

    def test_tool_doc_accessible(self, registry):
        """Tool docstring accessible via both .doc and __doc__."""
        executor = CodeExecutionTool(registry)
        # .doc property
        result = executor.execute("print(add.doc)")
        assert "Add two numbers" in result
        # __doc__ (for help())
        result2 = executor.execute("print(add.__doc__)")
        assert "Add two numbers" in result2

    def test_multiline_computation(self, registry):
        executor = CodeExecutionTool(registry)
        code = (
            "results = []\n"
            "for i in range(5):\n"
            "    results.append(add(a=i, b=i*10))\n"
            "print(results)"
        )
        result = executor.execute(code)
        assert "[0, 11, 22, 33, 44]" in result

    def test_syntax_error_rejected(self, registry):
        executor = CodeExecutionTool(registry)
        with pytest.raises(SyntaxError):
            executor.execute("def")


class TestRegistryIntegration:
    def test_enable_code_execution(self, registry):
        executor = registry.enable_code_execution()
        assert CODE_EXECUTION_NAME in registry
        assert executor is not None

    def test_enable_idempotent(self, registry):
        e1 = registry.enable_code_execution()
        e2 = registry.enable_code_execution()
        assert e1 is e2

    def test_disable_code_execution(self, registry):
        registry.enable_code_execution()
        assert CODE_EXECUTION_NAME in registry
        registry.disable_code_execution()
        assert CODE_EXECUTION_NAME not in registry

    def test_disable_noop_when_not_enabled(self, registry):
        registry.disable_code_execution()  # should not raise

    def test_code_execution_tool_schema(self, registry):
        registry.enable_code_execution()
        tool = registry.get_tool(CODE_EXECUTION_NAME)
        assert tool is not None
        assert "code" in tool.parameters.get("properties", {})

    def test_execute_via_registry(self, registry):
        registry.enable_code_execution()
        tool = registry.get_tool(CODE_EXECUTION_NAME)
        result = tool.run({"code": "print(42)"})
        assert "42" in result

    def test_execute_tool_call_via_registry(self, registry):
        """Full end-to-end: LLM tool call → code execution → tool invocation."""
        registry.enable_code_execution()
        tool = registry.get_tool(CODE_EXECUTION_NAME)
        result = tool.run({"code": "print(add(a=100, b=200))"})
        assert "300" in result
