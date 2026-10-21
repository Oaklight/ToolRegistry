"""Tests for the structural LangChain integration.

These tests need no LangChain install: the integration accepts any object with
``name``, ``description``, a schema source, and a runner.  Real
``langchain_core.tools.BaseTool`` coverage lives in ``test_langchain_compat.py``.
"""

from typing import Any

import pytest

from toolregistry import ToolRegistry
from toolregistry.integrations.langchain.integration import (
    LangChainIntegration,
    LangChainTool,
    LangChainToolWrapper,
)


# ---------------------------------------------------------------------------
# Mock LangChain-style tools
# ---------------------------------------------------------------------------


class _Schema:
    """Minimal pydantic-model stand-in."""

    def __init__(self, schema: dict[str, Any]) -> None:
        self._schema = schema

    def model_json_schema(self) -> dict[str, Any]:
        return dict(self._schema)


_ADD_SCHEMA = {
    "type": "object",
    "properties": {
        "a": {"type": "integer", "description": "First number"},
        "b": {"type": "integer", "description": "Second number"},
    },
    "required": ["a", "b"],
}


class MockAddTool:
    """A mock tool that adds two numbers (args-dict schema source)."""

    name = "add_numbers"
    description = "Add two numbers together"
    args = {
        "a": {"type": "integer", "description": "First number"},
        "b": {"type": "integer", "description": "Second number"},
    }

    def _run(self, a: int, b: int) -> int:
        return a + b

    async def _arun(self, a: int, b: int) -> int:
        return a + b


class MockUpperTool:
    """A mock tool that uppercases a string."""

    name = "upper_case"
    description = "Convert text to uppercase"
    args = {"text": {"type": "string"}}

    def _run(self, text: str) -> str:
        return text.upper()

    async def _arun(self, text: str) -> str:
        return text.upper()


class MockFailTool:
    """A mock tool that always fails."""

    name = "fail_tool"
    description = "Always fails"
    args: dict[str, Any] = {}

    def _run(self, **kwargs: Any) -> str:
        raise RuntimeError("Intentional failure")

    async def _arun(self, **kwargs: Any) -> str:
        raise RuntimeError("Intentional async failure")


class MockNoArgsTool:
    """A mock tool with no arguments."""

    name = "no_args_tool"
    description = "A tool that takes no arguments"
    args: dict[str, Any] = {}

    def _run(self) -> str:
        return "done"

    async def _arun(self) -> str:
        return "done"


class MockSyncOnlyTool:
    """A mock tool with no async runner."""

    name = "sync_only"
    description = "Sync only"
    args = {"x": {"type": "integer"}}

    def _run(self, x: int) -> int:
        return x + 1


class MockInputSchemaTool:
    """A mock tool whose ``input_schema`` is a pydantic-model stand-in."""

    name = "input_schema_tool"
    description = "Uses input_schema"
    input_schema = _Schema(_ADD_SCHEMA)

    def _run(self, a: int, b: int) -> int:
        return a + b


class MockArgsSchemaTool:
    """A mock tool whose ``args_schema`` is a pydantic-model stand-in."""

    name = "args_schema_tool"
    description = "Uses args_schema"
    args_schema = _Schema(_ADD_SCHEMA)

    def _run(self, a: int, b: int) -> int:
        return a + b


class MockParametersTool:
    """A mock tool that already exposes a JSON-schema ``parameters`` dict."""

    name = "parameters_tool"
    description = "Uses parameters"
    parameters = dict(_ADD_SCHEMA)

    def _run(self, a: int, b: int) -> int:
        return a + b


class MockNoSchemaTool:
    """A mock tool with no usable schema source."""

    name = "no_schema"
    description = "No schema"

    def _run(self) -> str:
        return "done"


class MockRunMethodTool:
    """A mock tool using the public ``run`` method instead of ``_run``."""

    name = "run_method"
    description = "Uses run()"
    args = {"x": {"type": "integer"}}

    def run(self, x: int) -> int:
        return x * 2


# ===========================================================================
# TestLangChainToolWrapper
# ===========================================================================


class TestLangChainToolWrapper:
    """Tests for LangChainToolWrapper."""

    def test_call_sync(self):
        """Sync call delegates to tool._run()."""
        lc_tool = MockAddTool()
        wrapper = LangChainToolWrapper(lc_tool)
        result = wrapper.call_sync(a=3, b=4)
        assert result == 7

    @pytest.mark.asyncio
    async def test_call_async(self):
        """Async call delegates to tool._arun()."""
        lc_tool = MockAddTool()
        wrapper = LangChainToolWrapper(lc_tool)
        result = await wrapper.call_async(a=10, b=20)
        assert result == 30

    @pytest.mark.asyncio
    async def test_call_async_falls_back_to_thread(self):
        """A sync-only tool still serves call_async()."""
        wrapper = LangChainToolWrapper(MockSyncOnlyTool())
        assert await wrapper.call_async(x=4) == 5

    def test_name_normalization(self):
        """Tool name is normalized."""
        lc_tool = MockAddTool()
        wrapper = LangChainToolWrapper(lc_tool)
        assert wrapper.name == "add_numbers"

    def test_params_extracted(self):
        """Parameter names are extracted from tool.args."""
        lc_tool = MockAddTool()
        wrapper = LangChainToolWrapper(lc_tool)
        assert set(wrapper.params) == {"a", "b"}

    def test_call_sync_exception_propagates(self):
        """Exceptions from tool._run() propagate."""
        lc_tool = MockFailTool()
        wrapper = LangChainToolWrapper(lc_tool)
        with pytest.raises(RuntimeError, match="Intentional failure"):
            wrapper.call_sync()

    @pytest.mark.asyncio
    async def test_call_async_exception_propagates(self):
        """Exceptions from tool._arun() propagate."""
        lc_tool = MockFailTool()
        wrapper = LangChainToolWrapper(lc_tool)
        with pytest.raises(RuntimeError, match="Intentional async failure"):
            await wrapper.call_async()

    def test_string_tool(self):
        """Wrapper works with string-based tools."""
        lc_tool = MockUpperTool()
        wrapper = LangChainToolWrapper(lc_tool)
        result = wrapper.call_sync(text="hello")
        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_string_tool_async(self):
        """Async wrapper works with string-based tools."""
        lc_tool = MockUpperTool()
        wrapper = LangChainToolWrapper(lc_tool)
        result = await wrapper.call_async(text="world")
        assert result == "WORLD"

    def test_run_method_is_accepted(self):
        """A plain ``run`` method is used when ``_run`` is absent."""
        wrapper = LangChainToolWrapper(MockRunMethodTool())
        assert wrapper.call_sync(x=21) == 42

    def test_missing_name_raises(self):
        class Unnamed:
            description = "no name"
            args: dict[str, Any] = {}

            def _run(self) -> str:
                return "x"

        with pytest.raises(TypeError, match="non-empty string 'name'"):
            LangChainToolWrapper(Unnamed())


# ===========================================================================
# TestLangChainTool
# ===========================================================================


class TestLangChainTool:
    """Tests for LangChainTool.from_langchain_tool()."""

    def test_basic_creation(self):
        """Creates a LangChainTool from a LangChain-style tool."""
        lc_tool = MockAddTool()
        tool = LangChainTool.from_langchain_tool(lc_tool)
        assert tool.name == "add_numbers"
        assert tool.description == "Add two numbers together"

    def test_parameters_schema(self):
        """Parameter schema is correctly extracted."""
        lc_tool = MockAddTool()
        tool = LangChainTool.from_langchain_tool(lc_tool)
        props = tool.parameters.get("properties", {})
        assert "a" in props
        assert "b" in props

    @pytest.mark.parametrize(
        "tool",
        [
            MockInputSchemaTool(),
            MockArgsSchemaTool(),
            MockParametersTool(),
        ],
    )
    def test_schema_source_fallbacks(self, tool):
        """input_schema, args_schema, and parameters are all accepted."""
        built = LangChainTool.from_langchain_tool(tool)
        props = built.parameters.get("properties", {})
        assert set(props) == {"a", "b"}

    def test_no_schema_raises(self):
        with pytest.raises(TypeError, match="no parameter schema"):
            LangChainTool.from_langchain_tool(MockNoSchemaTool())

    def test_with_namespace(self):
        """Namespace is applied to tool name."""
        lc_tool = MockAddTool()
        tool = LangChainTool.from_langchain_tool(lc_tool, namespace="math")
        assert "math" in tool.name

    def test_without_namespace(self):
        """Without namespace, name is plain."""
        lc_tool = MockAddTool()
        tool = LangChainTool.from_langchain_tool(lc_tool)
        assert tool.name == "add_numbers"

    def test_description_preserved(self):
        """Description from the tool is preserved."""
        lc_tool = MockUpperTool()
        tool = LangChainTool.from_langchain_tool(lc_tool)
        assert tool.description == "Convert text to uppercase"

    def test_tool_is_callable(self):
        """Created tool has a callable wrapper."""
        lc_tool = MockAddTool()
        tool = LangChainTool.from_langchain_tool(lc_tool)
        assert tool.callable is not None
        result = tool.callable.call_sync(a=5, b=6)
        assert result == 11

    def test_no_args_tool(self):
        """Tool with no args_schema works."""
        lc_tool = MockNoArgsTool()
        tool = LangChainTool.from_langchain_tool(lc_tool)
        assert tool.name == "no_args_tool"


# ===========================================================================
# TestLangChainIntegration
# ===========================================================================


class TestLangChainIntegration:
    """Tests for LangChainIntegration."""

    def test_register_single_tool(self):
        """Register a single LangChain-style tool."""
        registry = ToolRegistry(name="test")
        integration = LangChainIntegration(registry)
        integration.register_langchain_tools(MockAddTool())
        assert registry.get_tool("add_numbers") is not None

    def test_register_with_namespace_string(self):
        """Register with a string namespace."""
        registry = ToolRegistry(name="test")
        integration = LangChainIntegration(registry)
        integration.register_langchain_tools(MockAddTool(), namespace="math")
        tool_names = [t.name for t in registry._tools.values()]
        assert any("math" in name for name in tool_names)

    def test_register_with_namespace_true(self):
        """Register with namespace=True uses default ns."""
        registry = ToolRegistry(name="test")
        integration = LangChainIntegration(registry)
        integration.register_langchain_tools(MockAddTool(), namespace=True)
        tool_names = [t.name for t in registry._tools.values()]
        assert any("langchain" in name.lower() for name in tool_names)

    def test_register_with_namespace_false(self):
        """Register with namespace=False uses no prefix."""
        registry = ToolRegistry(name="test")
        integration = LangChainIntegration(registry)
        integration.register_langchain_tools(MockUpperTool(), namespace=False)
        assert registry.get_tool("upper_case") is not None

    def test_register_multiple_tools(self):
        """Register multiple different tools."""
        registry = ToolRegistry(name="test")
        integration = LangChainIntegration(registry)
        integration.register_langchain_tools(MockAddTool())
        integration.register_langchain_tools(MockUpperTool())
        assert registry.get_tool("add_numbers") is not None
        assert registry.get_tool("upper_case") is not None

    @pytest.mark.asyncio
    async def test_register_async(self):
        """Async registration works."""
        registry = ToolRegistry(name="test")
        integration = LangChainIntegration(registry)
        await integration.register_langchain_tools_async(MockAddTool())
        assert registry.get_tool("add_numbers") is not None


# ===========================================================================
# TestLangChainEndToEnd
# ===========================================================================


class TestLangChainEndToEnd:
    """End-to-end: register LangChain-style tools, call through registry."""

    def test_sync_end_to_end(self):
        """Register and call synchronously through the registry."""
        registry = ToolRegistry(name="test")
        integration = LangChainIntegration(registry)
        integration.register_langchain_tools(MockAddTool())

        fn = registry.get_callable("add_numbers")
        assert fn is not None
        result = fn(a=100, b=200)
        assert result == 300

    def test_sync_string_tool_end_to_end(self):
        """Register and call a string tool through the registry."""
        registry = ToolRegistry(name="test")
        integration = LangChainIntegration(registry)
        integration.register_langchain_tools(MockUpperTool())

        fn = registry.get_callable("upper_case")
        assert fn is not None
        result = fn(text="hello world")
        assert result == "HELLO WORLD"

    @pytest.mark.asyncio
    async def test_async_end_to_end(self):
        """Register and call asynchronously through the registry."""
        registry = ToolRegistry(name="test")
        integration = LangChainIntegration(registry)
        await integration.register_langchain_tools_async(MockAddTool())

        fn = registry.get_callable("add_numbers")
        assert fn is not None
        result = await fn.call_async(a=7, b=8)
        assert result == 15

    def test_error_propagation_end_to_end(self):
        """Errors from tool execution propagate through the registry."""
        registry = ToolRegistry(name="test")
        integration = LangChainIntegration(registry)
        integration.register_langchain_tools(MockFailTool())

        fn = registry.get_callable("fail_tool")
        assert fn is not None
        with pytest.raises(RuntimeError, match="Intentional failure"):
            fn()
