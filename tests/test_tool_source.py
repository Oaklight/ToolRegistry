"""Tests for ToolMetadata.source and ToolMetadata.source_detail fields."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from toolregistry import Tool, ToolMetadata


# ---------------------------------------------------------------------------
# Native tools
# ---------------------------------------------------------------------------


def _dummy(x: int) -> int:
    """Return x."""
    return x


class TestNativeToolSource:
    """Native tools should default to source='native' with empty detail."""

    def test_default_source(self):
        m = ToolMetadata()
        assert m.source == "native"
        assert m.source_detail == ""

    def test_from_function_default_source(self):
        tool = Tool.from_function(_dummy)
        assert tool.metadata.source == "native"
        assert tool.metadata.source_detail == ""

    def test_explicit_source_override(self):
        m = ToolMetadata(source="custom", source_detail="some detail")
        assert m.source == "custom"
        assert m.source_detail == "some detail"


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


class TestMCPToolSource:
    """MCPTool.from_tool_json should set source='mcp'."""

    def test_mcp_source_with_url_transport(self):
        mcp_types = pytest.importorskip("mcp.types")

        from toolregistry.integrations.mcp.integration import MCPTool

        tool_spec = mcp_types.Tool(
            name="echo",
            description="Echo input",
            inputSchema={"type": "object", "properties": {"msg": {"type": "string"}}},
        )

        connection = MagicMock()
        connection.transport = "http://localhost:8080/sse"

        tool = MCPTool.from_tool_json(tool_spec, connection=connection)
        assert tool.metadata.source == "mcp"
        assert tool.metadata.source_detail == "http://localhost:8080/sse"

    def test_mcp_source_with_stdio_transport(self):
        mcp_types = pytest.importorskip("mcp.types")

        from toolregistry.integrations.mcp.integration import MCPTool

        tool_spec = mcp_types.Tool(
            name="greet",
            description="Greet user",
            inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
        )

        connection = MagicMock()
        connection.transport = {"command": "uvx", "args": ["my-server"]}

        tool = MCPTool.from_tool_json(tool_spec, connection=connection)
        assert tool.metadata.source == "mcp"
        assert tool.metadata.source_detail == "stdio:uvx my-server"


# ---------------------------------------------------------------------------
# OpenAPI tools
# ---------------------------------------------------------------------------


class TestOpenAPIToolSource:
    """OpenAPITool.from_openapi_spec should set source='openapi'."""

    def test_openapi_source(self):
        pytest.importorskip("jsonref")

        from toolregistry.integrations.openapi.integration import OpenAPITool
        from toolregistry.utils import HttpxClientConfig

        client_config = HttpxClientConfig(base_url="https://api.example.com")
        spec: dict[str, Any] = {
            "operationId": "listItems",
            "summary": "List items",
            "parameters": [],
        }

        tool = OpenAPITool.from_openapi_spec(
            client_config=client_config,
            path="/items",
            method="get",
            spec=spec,
        )
        assert tool.metadata.source == "openapi"
        assert tool.metadata.source_detail == "https://api.example.com/items"


# ---------------------------------------------------------------------------
# LangChain tools
# ---------------------------------------------------------------------------


class TestLangChainToolSource:
    """LangChainTool.from_langchain_tool should set source='langchain'."""

    def test_langchain_source(self):
        pytest.importorskip("langchain_core")

        from langchain_core.tools import BaseTool as LCBaseTool
        from pydantic import BaseModel, Field

        from toolregistry.integrations.langchain.integration import LangChainTool

        class AddInput(BaseModel):
            """Input for adding two numbers."""

            a: int = Field(description="First number")
            b: int = Field(description="Second number")

        class MockAddTool(LCBaseTool):
            name: str = "add_numbers"
            description: str = "Add two numbers together"
            args_schema: type[BaseModel] = AddInput

            def _run(self, a: int, b: int) -> int:
                return a + b

            async def _arun(self, a: int, b: int) -> int:
                return a + b

        lc_tool = MockAddTool()
        tool = LangChainTool.from_langchain_tool(lc_tool)
        assert tool.metadata.source == "langchain"
        # source_detail should contain the class name
        assert "MockAddTool" in tool.metadata.source_detail
