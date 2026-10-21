"""Compatibility tests against real ``langchain-core`` BaseTool classes.

Skipped unless LangChain is installed; the scheduled drift workflow and the
dedicated CI job install it explicitly.  The rest of the integration test suite
uses structural fakes and needs no LangChain package.
"""

from typing import Any

import pytest

langchain_core = pytest.importorskip("langchain_core")

from langchain_core.tools import BaseTool  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from toolregistry import ToolRegistry  # noqa: E402


class AddInput(BaseModel):
    """Input for adding two numbers."""

    a: int = Field(description="First number")
    b: int = Field(description="Second number")


class RealAddTool(BaseTool):
    """A real BaseTool with an explicit args schema."""

    name: str = "add_numbers"
    description: str = "Add two numbers together"
    args_schema: type[BaseModel] = AddInput

    def _run(self, a: int, b: int) -> int:
        return a + b

    async def _arun(self, a: int, b: int) -> int:
        return a + b


class RealNoSchemaTool(BaseTool):
    """A real BaseTool whose schema is inferred from ``_run``."""

    name: str = "double"
    description: str = "Double an integer"

    def _run(self, value: int) -> int:
        return value * 2


class IncrementInput(BaseModel):
    """Input for incrementing."""

    value: int = Field(description="Value")


class RealSyncOnlyTool(BaseTool):
    """A real BaseTool with no async implementation."""

    name: str = "increment"
    description: str = "Increment an integer"
    args_schema: type[BaseModel] = IncrementInput

    def _run(self, value: int) -> int:
        return value + 1


def _register(tool: Any, **kwargs) -> ToolRegistry:
    registry = ToolRegistry(name="lc")
    registry.register(tool, source="langchain", **kwargs)
    return registry


class TestRealBaseTool:
    def test_sync_registration_and_invoke(self):
        registry = _register(RealAddTool())
        assert registry.invoke("add_numbers", {"a": 2, "b": 3}).result == "5"

    def test_schema_extraction(self):
        registry = _register(RealAddTool())
        tool = registry.get_tool("add_numbers")
        assert tool is not None
        assert set(tool.parameters["properties"]) == {"a", "b"}

    def test_async_registration_and_invoke(self):
        registry = ToolRegistry(name="lc")

        async def run():
            await registry.register_async(RealAddTool(), source="langchain")
            return await registry.ainvoke("add_numbers", {"a": 4, "b": 5})

        import asyncio

        result = asyncio.run(run())
        assert result.result == "9"

    def test_sync_only_tool_serves_async(self):
        registry = _register(RealSyncOnlyTool())
        import asyncio

        result = asyncio.run(registry.ainvoke("increment", {"value": 9}))
        assert result.result == "10"

    def test_inferred_schema(self):
        registry = _register(RealNoSchemaTool())
        tool = registry.get_tool("double")
        assert tool is not None
        assert set(tool.parameters["properties"]) == {"value"}

    def test_namespace_registration(self):
        registry = _register(RealAddTool(), namespace="math")
        assert registry.get_tool("math-add_numbers") is not None
