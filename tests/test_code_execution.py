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
        """Tool docstring accessible via __doc__ (for help())."""
        executor = CodeExecutionTool(registry)
        result = executor.execute("print(add.__doc__)")
        assert "Add two numbers" in result

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


class TestExecutionTrace:
    def test_trace_records_tool_calls(self, registry):
        executor = CodeExecutionTool(registry)
        executor.execute("x = add(a=1, b=2)\ny = multiply(a=x, b=3)\nprint(y)")
        trace = executor.last_trace
        assert trace is not None
        assert len(trace.tool_calls) == 2
        assert trace.tool_calls[0].tool_name == "add"
        assert trace.tool_calls[0].kwargs == {"a": 1, "b": 2}
        assert trace.tool_calls[0].result == 3
        assert trace.tool_calls[0].error is None
        assert trace.tool_calls[1].tool_name == "multiply"
        assert trace.tool_calls[1].result == 9

    def test_trace_records_errors(self, registry):
        def failing_tool(x: int) -> int:
            """Always fails."""
            raise ValueError("broken")

        registry.register(failing_tool)
        executor = CodeExecutionTool(registry)
        executor.execute(
            "try:\n    failing_tool(x=1)\nexcept ValueError:\n    print('caught')"
        )
        trace = executor.last_trace
        assert len(trace.tool_calls) == 1
        assert trace.tool_calls[0].error == "broken"

    def test_trace_has_duration(self, registry):
        executor = CodeExecutionTool(registry)
        executor.execute("add(a=1, b=2)")
        assert executor.last_trace.tool_calls[0].duration_ms >= 0

    def test_trace_stores_code(self, registry):
        code = "print(add(a=5, b=5))"
        executor = CodeExecutionTool(registry)
        executor.execute(code)
        assert executor.last_trace.code == code

    def test_no_trace_before_execution(self, registry):
        executor = CodeExecutionTool(registry)
        assert executor.last_trace is None

    def test_trace_empty_when_no_tools_called(self, registry):
        executor = CodeExecutionTool(registry)
        executor.execute("print(42)")
        assert executor.last_trace is not None
        assert len(executor.last_trace.tool_calls) == 0


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
