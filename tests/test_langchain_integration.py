"""Tests for LangChain integration module."""

from typing import Any

import pytest

langchain_core = pytest.importorskip("langchain_core")

from langchain_core.tools import BaseTool as LCBaseTool  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from toolregistry import ToolRegistry  # noqa: E402
from toolregistry.integrations.langchain.integration import (  # noqa: E402
    LangChainIntegration,
    LangChainTool,
    LangChainToolWrapper,
)


# ---------------------------------------------------------------------------
# Mock LangChain tools
# ---------------------------------------------------------------------------


class AddInput(BaseModel):
    """Input for adding two numbers."""

    a: int = Field(description="First number")
    b: int = Field(description="Second number")


class MockAddTool(LCBaseTool):
    """A mock tool that adds two numbers."""

    name: str = "add_numbers"
    description: str = "Add two numbers together"
    args_schema: type[BaseModel] = AddInput

    def _run(self, a: int, b: int) -> int:
        return a + b

    async def _arun(self, a: int, b: int) -> int:
        return a + b


class MockUpperTool(LCBaseTool):
    """A mock tool that uppercases a string."""

    name: str = "upper_case"
    description: str = "Convert text to uppercase"

    def _run(self, text: str) -> str:
        return text.upper()

    async def _arun(self, text: str) -> str:
        return text.upper()


class MockFailTool(LCBaseTool):
    """A mock tool that always fails."""

    name: str = "fail_tool"
    description: str = "Always fails"

    def _run(self, **kwargs: Any) -> str:
        raise RuntimeError("Intentional failure")

    async def _arun(self, **kwargs: Any) -> str:
        raise RuntimeError("Intentional async failure")


class MockNoArgsTool(LCBaseTool):
    """A mock tool with no arguments."""

    name: str = "no_args_tool"
    description: str = "A tool that takes no arguments"

    def _run(self) -> str:
        return "done"

    async def _arun(self) -> str:
        return "done"


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


# ===========================================================================
# TestLangChainTool
# ===========================================================================


class TestLangChainTool:
    """Tests for LangChainTool.from_langchain_tool()."""

    def test_basic_creation(self):
        """Creates a LangChainTool from a LangChain tool."""
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
        """Description from LangChain tool is preserved."""
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
        """Register a single LangChain tool."""
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
    """End-to-end: register LangChain tools, call through registry."""

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
