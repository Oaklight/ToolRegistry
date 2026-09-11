"""Tests for remote tool source refresh (OpenAPI + MCP)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from toolregistry import ToolRegistry
from toolregistry.events import ChangeEvent, ChangeEventType, RefreshResult
from toolregistry.integrations.openapi.integration import (
    OpenAPIIntegration,
)
from toolregistry.utils import HttpClientConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SPEC_V1 = {
    "openapi": "3.0.0",
    "info": {"title": "TestAPI", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "summary": "List items",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    }
                ],
            },
        },
        "/items/{id}": {
            "get": {
                "operationId": "getItem",
                "summary": "Get one item",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
            },
        },
    },
}

SPEC_V2_ADDED = {
    **SPEC_V1,
    "paths": {
        **SPEC_V1["paths"],
        "/items": {
            **SPEC_V1["paths"]["/items"],
            "post": {
                "operationId": "createItem",
                "summary": "Create item",
                "parameters": [],
            },
        },
    },
}

SPEC_V2_REMOVED = {
    **SPEC_V1,
    "paths": {
        "/items": SPEC_V1["paths"]["/items"],
    },
}

SPEC_V2_UPDATED = {
    **SPEC_V1,
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "summary": "List all items (v2)",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    },
                ],
            },
        },
        "/items/{id}": SPEC_V1["paths"]["/items/{id}"],
    },
}


def _make_client_config(base_url: str = "http://test.example.com") -> HttpClientConfig:
    return HttpClientConfig(base_url=base_url)


# ---------------------------------------------------------------------------
# RefreshResult
# ---------------------------------------------------------------------------


class TestRefreshResult:
    def test_defaults(self):
        r = RefreshResult(source="openapi")
        assert r.source == "openapi"
        assert r.added == ()
        assert r.removed == ()
        assert r.updated == ()
        assert r.unchanged == 0
        assert r.skipped is False
        assert r.changed is False

    def test_changed_property(self):
        assert RefreshResult(source="mcp", added=("x",)).changed is True
        assert RefreshResult(source="mcp", removed=("x",)).changed is True
        assert RefreshResult(source="mcp", updated=("x",)).changed is True
        assert RefreshResult(source="mcp", unchanged=5).changed is False
        assert RefreshResult(source="mcp", skipped=True).changed is False


# ---------------------------------------------------------------------------
# _unregister
# ---------------------------------------------------------------------------


class TestUnregister:
    def test_removes_tool_and_emits_event(self):
        registry = ToolRegistry()
        registry.register(lambda x: x, name="my_tool")
        assert "my_tool" in registry._tools

        events: list[ChangeEvent] = []
        registry.on_change(events.append)

        result = registry._unregister("my_tool")
        assert result is True
        assert "my_tool" not in registry._tools
        assert any(
            e.event_type == ChangeEventType.UNREGISTER and e.tool_name == "my_tool"
            for e in events
        )

    def test_cleans_disabled_state(self):
        registry = ToolRegistry()
        registry.register(lambda x: x, name="my_tool")
        registry.disable("my_tool", "test reason")
        assert not registry.is_enabled("my_tool")

        registry._unregister("my_tool")
        assert "my_tool" not in registry._disabled

    def test_returns_false_for_nonexistent(self):
        registry = ToolRegistry()
        assert registry._unregister("nonexistent") is False


# ---------------------------------------------------------------------------
# OpenAPI refresh
# ---------------------------------------------------------------------------


class TestOpenAPIRefresh:
    def _register(self, registry, spec=None, namespace=False, spec_url=None):
        spec = spec or SPEC_V1
        client = _make_client_config()
        registry.register_from_openapi(
            client, spec, namespace=namespace, spec_url=spec_url
        )

    def test_refresh_unchanged(self):
        registry = ToolRegistry()
        self._register(registry)
        result = registry.refresh_from_openapi(openapi_spec=SPEC_V1)
        assert result.skipped is False
        assert result.changed is False
        assert result.unchanged == 2

    def test_refresh_add_tool(self):
        registry = ToolRegistry()
        self._register(registry)
        initial_count = len(registry._tools)

        result = registry.refresh_from_openapi(openapi_spec=SPEC_V2_ADDED)
        assert "create_item" in result.added
        assert len(registry._tools) == initial_count + 1

    def test_refresh_remove_tool(self):
        registry = ToolRegistry()
        self._register(registry)
        assert "get_item" in registry._tools

        result = registry.refresh_from_openapi(openapi_spec=SPEC_V2_REMOVED)
        assert "get_item" in result.removed
        assert "get_item" not in registry._tools

    def test_refresh_update_tool(self):
        registry = ToolRegistry()
        self._register(registry)

        result = registry.refresh_from_openapi(openapi_spec=SPEC_V2_UPDATED)
        assert "list_items" in result.updated
        updated_tool = registry._tools["list_items"]
        assert "offset" in updated_tool.parameters.get("properties", {})

    def test_refresh_preserves_disabled_state(self):
        registry = ToolRegistry()
        self._register(registry)
        registry.disable("list_items", "maintenance")

        registry.refresh_from_openapi(openapi_spec=SPEC_V1)
        assert not registry.is_enabled("list_items")
        assert registry.get_disable_reason("list_items") == "maintenance"

    def test_refresh_removes_disabled_for_removed_tools(self):
        registry = ToolRegistry()
        self._register(registry)
        registry.disable("get_item", "test")

        registry.refresh_from_openapi(openapi_spec=SPEC_V2_REMOVED)
        assert "get_item" not in registry._disabled

    def test_refresh_with_namespace(self):
        registry = ToolRegistry()
        self._register(registry, namespace="api")
        assert "api-list_items" in registry._tools

        result = registry.refresh_from_openapi(openapi_spec=SPEC_V2_ADDED)
        assert any("create_item" in name for name in result.added)

    def test_refresh_emits_events(self):
        registry = ToolRegistry()
        self._register(registry)

        events: list[ChangeEvent] = []
        registry.on_change(events.append)

        registry.refresh_from_openapi(openapi_spec=SPEC_V2_UPDATED)

        refresh_events = [e for e in events if e.event_type == ChangeEventType.REFRESH]
        assert len(refresh_events) >= 1

    def test_refresh_no_spec_url_no_stored_spec_raises(self):
        registry = ToolRegistry()
        integration = OpenAPIIntegration(registry)
        with pytest.raises(ValueError, match="Cannot refresh"):
            integration.refresh()

    def test_refresh_uses_stored_spec(self):
        registry = ToolRegistry()
        self._register(registry)
        integration = registry._openapi_integrations[0]
        assert integration._openapi_spec is not None

        result = integration.refresh()
        assert result.unchanged == 2


# ---------------------------------------------------------------------------
# OpenAPI ETag conditional fetch
# ---------------------------------------------------------------------------


class TestOpenAPIConditionalFetch:
    @pytest.mark.asyncio
    async def test_etag_304(self):
        from toolregistry._vendor.httpclient import Response

        mock_response = Response(304, {}, b"", "http://test.example.com/openapi.json")

        with patch("toolregistry.integrations.openapi.utils.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            from toolregistry.integrations.openapi.utils import (
                load_openapi_spec_conditional_async,
            )

            spec, etag = await load_openapi_spec_conditional_async(
                "http://test.example.com/openapi.json", etag='"abc123"'
            )
            assert spec is None
            assert etag == '"abc123"'

    @pytest.mark.asyncio
    async def test_etag_200_with_new_etag(self):
        from toolregistry._vendor.httpclient import Response

        spec_bytes = json.dumps(SPEC_V1).encode()
        mock_response = Response(
            200,
            {"content-type": "application/json", "ETag": '"new-etag"'},
            spec_bytes,
            "http://test.example.com/openapi.json",
        )

        with patch("toolregistry.integrations.openapi.utils.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            from toolregistry.integrations.openapi.utils import (
                load_openapi_spec_conditional_async,
            )

            spec, etag = await load_openapi_spec_conditional_async(
                "http://test.example.com/openapi.json"
            )
            assert spec is not None
            assert etag == '"new-etag"'


# ---------------------------------------------------------------------------
# refresh_all
# ---------------------------------------------------------------------------


class TestRefreshAll:
    def test_refresh_all_single_openapi(self):
        registry = ToolRegistry()
        client = _make_client_config()
        registry.register_from_openapi(client, SPEC_V1)

        events: list[ChangeEvent] = []
        registry.on_change(events.append)

        results = registry.refresh_all()
        assert len(results) == 1
        assert results[0].source == "openapi"
        assert any(e.event_type == ChangeEventType.REFRESH_ALL for e in events)

    def test_refresh_all_empty(self):
        registry = ToolRegistry()
        results = registry.refresh_all()
        assert results == []


# ---------------------------------------------------------------------------
# Background polling
# ---------------------------------------------------------------------------


class TestPolling:
    def test_openapi_start_stop_polling(self):
        registry = ToolRegistry()
        client = _make_client_config()
        registry.register_from_openapi(client, SPEC_V1)
        integration = registry._openapi_integrations[0]

        integration.start_polling(100.0)
        assert integration._poll_timer is not None
        assert integration._poll_timer.is_alive()

        integration.stop_polling()
        assert integration._poll_timer is None
        assert integration._poll_interval is None

    def test_close_stops_polling(self):
        registry = ToolRegistry()
        client = _make_client_config()
        registry.register_from_openapi(client, SPEC_V1)
        integration = registry._openapi_integrations[0]

        integration.start_polling(100.0)
        assert integration._poll_timer is not None

        registry.close()
        assert integration._poll_timer is None
        assert integration._poll_interval is None


# ---------------------------------------------------------------------------
# MCP refresh (mocked)
# ---------------------------------------------------------------------------


class _MockToolSpec:
    """Minimal stand-in for mcp.types.Tool."""

    def __init__(self, name, description="", input_schema=None):
        self.name = name
        self.description = description
        self.input_schema = input_schema or {"type": "object", "properties": {}}


class TestMCPRefresh:
    """Tests for MCPIntegration.refresh() using mocked MCP clients."""

    def _make_integration(self, registry, tool_specs):
        """Register mocked MCP tools and return the integration."""
        from toolregistry.integrations.mcp.integration import (
            MCPIntegration,
            MCPTool,
        )
        from toolregistry.integrations.mcp.connection import MCPConnectionManager

        integration = MCPIntegration(registry)
        connection = MagicMock(spec=MCPConnectionManager)
        connection.transport = "http://mock-mcp:8000"
        integration._connections.append(connection)
        integration._transport = "http://mock-mcp:8000"
        integration._resolved_ns = None
        integration._persistent = True
        integration._headers = None

        sep = getattr(registry, "_name_sep", "-")
        for ts in tool_specs:
            tool = MCPTool.from_tool_json(ts, connection, namespace=None)
            tool = tool.update_namespace(None, force=True, sep=sep)
            registry.register(tool)
            integration._registered_tool_names.add(tool.name)

        return integration

    def _patch_mcp_client(self, tool_specs):
        """Return a context manager that mocks MCPClient to return given specs."""
        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=tool_specs)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return patch(
            "toolregistry.integrations.mcp.integration.MCPClient",
            return_value=mock_client,
        )

    def test_mcp_refresh_unchanged(self):
        specs = [_MockToolSpec("add"), _MockToolSpec("multiply")]
        registry = ToolRegistry()
        integration = self._make_integration(registry, specs)

        with self._patch_mcp_client(specs):
            result = integration.refresh()

        assert result.changed is False
        assert result.unchanged == 2

    def test_mcp_refresh_add_tool(self):
        initial = [_MockToolSpec("add")]
        updated = [_MockToolSpec("add"), _MockToolSpec("subtract")]
        registry = ToolRegistry()
        integration = self._make_integration(registry, initial)

        with self._patch_mcp_client(updated):
            result = integration.refresh()

        assert "subtract" in result.added
        assert "subtract" in registry._tools

    def test_mcp_refresh_remove_tool(self):
        initial = [_MockToolSpec("add"), _MockToolSpec("multiply")]
        updated = [_MockToolSpec("add")]
        registry = ToolRegistry()
        integration = self._make_integration(registry, initial)

        with self._patch_mcp_client(updated):
            result = integration.refresh()

        assert "multiply" in result.removed
        assert "multiply" not in registry._tools

    def test_mcp_refresh_update_tool(self):
        initial = [_MockToolSpec("add", description="Add numbers")]
        changed = [_MockToolSpec("add", description="Add two integers")]
        registry = ToolRegistry()
        integration = self._make_integration(registry, initial)

        with self._patch_mcp_client(changed):
            result = integration.refresh()

        assert "add" in result.updated
        assert registry._tools["add"].description == "Add two integers"

    def test_mcp_refresh_preserves_disabled_state(self):
        specs = [_MockToolSpec("add"), _MockToolSpec("multiply")]
        registry = ToolRegistry()
        integration = self._make_integration(registry, specs)
        registry.disable("add", "maintenance")

        with self._patch_mcp_client(specs):
            integration.refresh()

        assert not registry.is_enabled("add")
        assert registry.get_disable_reason("add") == "maintenance"
