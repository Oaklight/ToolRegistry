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

    def test_timeout(self, registry):
        executor = CodeExecutionTool(registry, timeout=1)
        result = executor.execute("import time; time.sleep(10)")
        # Timeout returns empty stdout
        assert result == "" or "Error" in result

    def test_dangerous_code_rejected(self, registry):
        executor = CodeExecutionTool(registry)
        with pytest.raises(ValueError, match="Import not allowed"):
            executor.execute("import os; os.system('ls')")

    def test_namespace_contains_tools(self, registry):
        executor = CodeExecutionTool(registry)
        result = executor.execute("print('add' in dir() and 'multiply' in dir())")
        assert result.strip() == "True"

    def test_namespace_excludes_self(self, registry):
        """code_execution tool should not be in its own namespace."""
        registry.enable_code_execution()
        executor = registry._code_execution
        result = executor.execute(f"print('{CODE_EXECUTION_NAME}' in dir())")
        assert result.strip() == "False"

    def test_namespace_stubs_raise(self, registry):
        executor = CodeExecutionTool(registry)
        code = "try:\n    add(a=1, b=2)\nexcept NotImplementedError:\n    print('stub')"
        result = executor.execute(code)
        assert result.strip() == "stub"

    def test_custom_timeout(self, registry):
        executor = CodeExecutionTool(registry, timeout=60)
        result = executor.execute("print('fast')", timeout=5)
        assert result.strip() == "fast"


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
