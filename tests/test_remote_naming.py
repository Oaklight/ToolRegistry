"""Cross-source naming and filter-ordering tests (#295, #296).

Registration and refresh must agree on the key a remote tool is stored
under, including when the registry uses ``name_sep="."``.  Filters must be
applied to that key before the tool wrapper is constructed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from toolregistry import ToolRegistry
from toolregistry.utils import HttpClientConfig

try:
    from toolregistry.integrations.mcp.integration import MCPIntegration, MCPTool

    _HAS_MCP = True
except ImportError:  # pragma: no cover - depends on the mcp extra
    MCPIntegration = None  # type: ignore[assignment]
    MCPTool = None  # type: ignore[assignment]
    _HAS_MCP = False

try:
    from toolregistry.integrations.langchain.integration import (
        LangChainIntegration,
        LangChainTool,
    )

    _HAS_LANGCHAIN = True
except ImportError:  # pragma: no cover - depends on the langchain extra
    LangChainIntegration = None  # type: ignore[assignment]
    LangChainTool = None  # type: ignore[assignment]
    _HAS_LANGCHAIN = False

requires_mcp = pytest.mark.skipif(not _HAS_MCP, reason="mcp extra not installed")
requires_langchain = pytest.mark.skipif(
    not _HAS_LANGCHAIN, reason="langchain extra not installed"
)


class _MockToolSpec:
    def __init__(self, name, description="", input_schema=None):
        self.name = name
        self.description = description
        self.input_schema = input_schema or {"type": "object", "properties": {}}


def _patch_mcp_client(tool_specs):
    mock_client = AsyncMock()
    mock_client.server_info = None
    mock_client.list_tools = AsyncMock(return_value=tool_specs)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "toolregistry.integrations.mcp.integration.MCPClient",
        return_value=mock_client,
    )


OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "TestAPI", "version": "1.0.0"},
    "paths": {
        "/items": {"get": {"operationId": "listItems", "summary": "List items"}},
    },
}

OPENAPI_SPEC_ADDED = {
    "openapi": "3.0.0",
    "info": {"title": "TestAPI", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {"operationId": "listItems", "summary": "List items"},
            "post": {"operationId": "createItem", "summary": "Create an item"},
        },
    },
}


# ---------------------------------------------------------------------------
# MCP
# ---------------------------------------------------------------------------


@requires_mcp
class TestMCPNaming:
    @pytest.mark.asyncio
    async def test_dotted_registration_and_refresh_agree(self):
        registry = ToolRegistry(name_sep=".")
        integration = MCPIntegration(registry)
        specs = [_MockToolSpec("list_issues")]

        with _patch_mcp_client(specs):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", namespace="gh", include=["gh.*"]
            )

        assert set(registry._tools) == {"gh.list_issues"}

        with _patch_mcp_client(specs):
            result = await integration.refresh_async()

        assert result.added == ()
        assert result.removed == ()
        assert result.unchanged == 1
        assert set(registry._tools) == {"gh.list_issues"}

    @pytest.mark.asyncio
    async def test_raw_dot_and_hyphen_names_normalize_before_qualification(self):
        registry = ToolRegistry(name_sep=".")
        integration = MCPIntegration(registry)
        specs = [_MockToolSpec("list.issues"), _MockToolSpec("get-issue")]

        with _patch_mcp_client(specs):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", namespace="gh", include=["gh.*"]
            )

        assert set(registry._tools) == {"gh.list_issues", "gh.get_issue"}

        with _patch_mcp_client(specs):
            result = await integration.refresh_async()

        assert result.added == ()
        assert result.removed == ()
        assert set(registry._tools) == {"gh.list_issues", "gh.get_issue"}

    @pytest.mark.asyncio
    async def test_dotted_refresh_reports_changed_set_with_prefix(self):
        registry = ToolRegistry(name_sep=".")
        integration = MCPIntegration(registry)
        initial = [_MockToolSpec("list_issues"), _MockToolSpec("get_issue")]

        with _patch_mcp_client(initial):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", namespace="gh", include=["gh.*"]
            )

        assert set(registry._tools) == {"gh.list_issues", "gh.get_issue"}

        refreshed = [_MockToolSpec("list_issues"), _MockToolSpec("create_issue")]
        with _patch_mcp_client(refreshed):
            result = await integration.refresh_async()

        assert result.added == ("gh.create_issue",)
        assert result.removed == ("gh.get_issue",)
        assert set(registry._tools) == {"gh.list_issues", "gh.create_issue"}

    @pytest.mark.asyncio
    async def test_dotted_refresh_reports_updated_tool(self):
        registry = ToolRegistry(name_sep=".")
        integration = MCPIntegration(registry)

        with _patch_mcp_client([_MockToolSpec("list_issues")]):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", namespace="gh", include=["gh.*"]
            )

        with _patch_mcp_client(
            [_MockToolSpec("list_issues", description="Updated description")]
        ):
            result = await integration.refresh_async()

        assert result.updated == ("gh.list_issues",)
        assert set(registry._tools) == {"gh.list_issues"}

    def test_excluded_tool_is_not_constructed(self):
        registry = ToolRegistry()
        integration = MCPIntegration(registry)

        with _patch_mcp_client([_MockToolSpec("add")]):
            with patch.object(
                MCPTool,
                "from_tool_json",
                side_effect=AssertionError("excluded tool was constructed"),
            ):
                with pytest.warns(UserWarning, match="excluded all 1"):
                    integration.register_mcp_tools(
                        "http://mock-mcp:8000", exclude=["add"]
                    )

        assert registry._tools == {}


# ---------------------------------------------------------------------------
# OpenAPI
# ---------------------------------------------------------------------------


class TestOpenAPINaming:
    def _register(self, registry, **kwargs):
        registry.register(
            HttpClientConfig(base_url="http://test.example.com"),
            source="openapi",
            openapi_spec=OPENAPI_SPEC,
            **kwargs,
        )

    def test_dotted_registration_and_refresh_agree(self):
        registry = ToolRegistry(name_sep=".")
        self._register(registry, namespace="gh", include=["gh.*"])

        assert set(registry._tools) == {"gh.list_items"}

        integration = registry._openapi_integrations[0]
        result = integration.refresh(openapi_spec=OPENAPI_SPEC)

        assert result.added == ()
        assert result.removed == ()
        assert set(registry._tools) == {"gh.list_items"}

    def test_dotted_refresh_reports_added_tool_with_prefix(self):
        registry = ToolRegistry(name_sep=".")
        self._register(registry, namespace="gh", include=["gh.*"])

        result = registry._openapi_integrations[0].refresh(
            openapi_spec=OPENAPI_SPEC_ADDED
        )

        assert result.added == ("gh.create_item",)
        assert set(registry._tools) == {"gh.list_items", "gh.create_item"}

    def test_excluded_malformed_operation_does_not_abort(self):
        spec = {
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "badOp",
                        # Missing "name": construction raises KeyError.
                        "parameters": [{"in": "query", "schema": {"type": "string"}}],
                    }
                }
            }
        }
        registry = ToolRegistry()

        with pytest.warns(UserWarning, match="excluded all 1"):
            registry.register(
                HttpClientConfig(base_url="http://x.test"),
                source="openapi",
                openapi_spec=spec,
                exclude=["badOp"],
            )

        assert registry._tools == {}

    def test_included_malformed_operation_still_raises(self):
        spec = {
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "badOp",
                        "parameters": [{"in": "query", "schema": {"type": "string"}}],
                    }
                }
            }
        }
        registry = ToolRegistry()

        with pytest.raises(ValueError, match="Failed to register OpenAPI tools"):
            registry.register(
                HttpClientConfig(base_url="http://x.test"),
                source="openapi",
                openapi_spec=spec,
                include=["badOp"],
            )


# ---------------------------------------------------------------------------
# LangChain
# ---------------------------------------------------------------------------


@requires_langchain
class TestLangChainNaming:
    def _tool(self):
        from tests.test_langchain_integration import MockAddTool

        return MockAddTool()

    def test_dotted_registration(self):
        registry = ToolRegistry(name_sep=".")
        registry.register(self._tool(), source="langchain", namespace="lc")
        assert set(registry._tools) == {"lc.add_numbers"}

    def test_excluded_tool_is_not_constructed(self):
        registry = ToolRegistry()
        integration = LangChainIntegration(registry)
        tool = MagicMock()
        tool.name = "add_numbers"

        with patch.object(
            LangChainTool,
            "from_langchain_tool",
            side_effect=AssertionError("excluded tool was constructed"),
        ):
            integration.register_langchain_tools(tool, exclude=["add_numbers"])

        assert registry._tools == {}
