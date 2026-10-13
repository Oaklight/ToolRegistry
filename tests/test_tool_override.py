"""Tests for first-class tool override.

Covers the ``override`` / ``restore_override`` / ``list_overrides`` API on
``RegistrationMixin``, the ``OVERRIDE`` change event, interaction with
``disable()`` and ``_unregister()``, and durability of local overrides
across MCP and OpenAPI refreshes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from toolregistry import ChangeEventType, Tool, ToolRegistry
from toolregistry.utils import HttpClientConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def multiply(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b


def add_offset(a: int, b: int) -> int:
    """Add two integers with an offset."""
    return a + b + 100


# ---------------------------------------------------------------------------
# override / restore_override / list_overrides
# ---------------------------------------------------------------------------


class TestOverrideApi:
    """Behaviour of the public override API."""

    def test_override_existing_tool(self):
        registry = ToolRegistry()
        registry.register(add)
        original = registry._tools["add"]

        replacement = registry.override("add", multiply)

        assert isinstance(replacement, Tool)
        assert registry._tools["add"] is replacement
        assert registry._tools["add"] is not original
        assert registry.list_overrides() == {"add": original}

    def test_override_missing_without_create_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError):
            registry.override("missing", add)

    def test_override_create_true_registers(self):
        registry = ToolRegistry()
        tool = registry.override("brand_new", add, create=True)

        assert registry._tools["brand_new"] is tool
        # Nothing was displaced, so no override is recorded.
        assert registry.list_overrides() == {}

    def test_override_create_true_restore_raises(self):
        registry = ToolRegistry()
        registry.override("brand_new", add, create=True)
        with pytest.raises(KeyError):
            registry.restore_override("brand_new")

    def test_restore_override_restores_original(self):
        registry = ToolRegistry()
        registry.register(add)
        original = registry._tools["add"]

        registry.override("add", multiply)
        restored = registry.restore_override("add")

        assert restored is original
        assert registry._tools["add"] is original
        assert registry.list_overrides() == {}

    def test_restore_without_override_raises(self):
        registry = ToolRegistry()
        registry.register(add)
        with pytest.raises(KeyError):
            registry.restore_override("add")

    def test_list_overrides_returns_copy(self):
        registry = ToolRegistry()
        registry.register(add)
        registry.override("add", multiply)

        snapshot = registry.list_overrides()
        snapshot.clear()
        assert "add" in registry.list_overrides()

    def test_unregister_drops_override(self):
        registry = ToolRegistry()
        registry.register(add)
        registry.override("add", multiply)

        assert registry._unregister("add") is True
        assert "add" not in registry._tools
        assert registry.list_overrides() == {}

    def test_override_preserves_disabled_state(self):
        registry = ToolRegistry()
        registry.register(add)
        registry.disable("add", "maintenance")

        registry.override("add", multiply)

        assert registry.is_enabled("add") is False
        assert registry.get_disable_reason("add") == "maintenance"

    def test_override_replaces_behavior(self):
        registry = ToolRegistry()
        registry.register(add)
        registry.override("add", multiply)

        result = registry.invoke("add", {"a": 2, "b": 3}, execution_mode="thread")
        assert result.result == "6"

    def test_repeated_override_keeps_original_restorable(self):
        registry = ToolRegistry()
        registry.register(add)
        original = registry._tools["add"]

        registry.override("add", multiply)
        registry.override("add", add_offset)

        assert registry.restore_override("add") is original

    def test_override_tool_instance_aligns_name(self):
        registry = ToolRegistry()
        registry.register(add)

        renamed = Tool.from_function(multiply, name="multiply")
        result = registry.override("add", renamed)

        assert result.name == "add"
        assert registry._tools["add"].name == "add"


# ---------------------------------------------------------------------------
# Change events
# ---------------------------------------------------------------------------


class TestOverrideEvents:
    """The OVERRIDE change event is emitted on override and restore."""

    def test_override_emits_override_event(self):
        registry = ToolRegistry()
        registry.register(add)
        events = []
        registry.on_change(events.append)

        registry.override("add", multiply)

        assert any(
            e.event_type == ChangeEventType.OVERRIDE and e.tool_name == "add"
            for e in events
        )

    def test_restore_emits_override_event(self):
        registry = ToolRegistry()
        registry.register(add)
        registry.override("add", multiply)
        events = []
        registry.on_change(events.append)

        registry.restore_override("add")

        override_events = [
            e for e in events if e.event_type == ChangeEventType.OVERRIDE
        ]
        assert len(override_events) == 1
        assert override_events[0].tool_name == "add"
        assert override_events[0].metadata.get("restored") is True


# ---------------------------------------------------------------------------
# MCP refresh durability
# ---------------------------------------------------------------------------


class _MockToolSpec:
    """Minimal stand-in for mcp.types.Tool."""

    def __init__(self, name, description="", input_schema=None):
        self.name = name
        self.description = description
        self.input_schema = input_schema or {"type": "object", "properties": {}}


def _make_mcp_integration(registry, tool_specs):
    """Register mocked MCP tools and return the integration."""
    from toolregistry.integrations.mcp.connection import MCPConnectionManager
    from toolregistry.integrations.mcp.integration import MCPIntegration, MCPTool

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


def _patch_mcp_client(tool_specs):
    """Return a context manager that mocks MCPClient to return given specs."""
    mock_client = AsyncMock()
    mock_client.list_tools = AsyncMock(return_value=tool_specs)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "toolregistry.integrations.mcp.integration.MCPClient",
        return_value=mock_client,
    )


class TestMcpRefreshHonorsOverride:
    """An MCP refresh must not revert a locally overridden tool."""

    def test_refresh_keeps_override_on_remote_update(self):
        registry = ToolRegistry()
        integration = _make_mcp_integration(registry, [_MockToolSpec("add")])
        replacement = registry.override("add", multiply)

        changed = [_MockToolSpec("add", description="Remote add changed")]
        with _patch_mcp_client(changed):
            result = integration.refresh()

        assert registry._tools["add"] is replacement
        assert "add" not in result.updated
        assert "add" not in result.removed

    def test_refresh_keeps_override_when_remote_removes_tool(self):
        registry = ToolRegistry()
        integration = _make_mcp_integration(registry, [_MockToolSpec("add")])
        replacement = registry.override("add", multiply)

        with _patch_mcp_client([]):
            result = integration.refresh()

        assert registry._tools["add"] is replacement
        assert "add" not in result.removed


# ---------------------------------------------------------------------------
# OpenAPI refresh durability
# ---------------------------------------------------------------------------

_OPENAPI_SPEC_V1 = {
    "openapi": "3.0.0",
    "info": {"title": "T", "version": "1.0.0"},
    "paths": {
        "/x": {
            "get": {
                "operationId": "getX",
                "summary": "Get X",
                "responses": {"200": {"description": "ok"}},
            }
        }
    },
}

_OPENAPI_SPEC_V2 = {
    "openapi": "3.0.0",
    "info": {"title": "T", "version": "1.0.0"},
    "paths": {
        "/x": {
            "get": {
                "operationId": "getX",
                "summary": "Get X (changed)",
                "responses": {"200": {"description": "ok"}},
            }
        }
    },
}


class TestOpenAPIRefreshHonorsOverride:
    """An OpenAPI refresh must not revert a locally overridden tool."""

    def test_refresh_keeps_override(self):
        registry = ToolRegistry()
        registry.register(
            HttpClientConfig(base_url="http://test.example.com"),
            source="openapi",
            openapi_spec=_OPENAPI_SPEC_V1,
        )
        name = next(iter(registry._tools))
        replacement = registry.override(name, multiply)

        result = registry.refresh_from_openapi(openapi_spec=_OPENAPI_SPEC_V2)

        assert registry._tools[name] is replacement
        assert name not in result.updated
        assert name not in result.removed
