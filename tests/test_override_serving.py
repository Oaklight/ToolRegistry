"""Serving-surface tests for an override kept across re-registration.

The registry's own view is not enough: a ``RouteTable`` — and every MCP client
built from it — holds a direct ``Tool`` reference and replaces it only when the
registry emits a change event.  Re-registering a source replaces the tools, so
reinstating an override must notify those listeners.  Without the event the
registry reports the override while MCP ``tools/list`` and ``call_tool`` keep
serving the source's definition.

The listener lives in ``toolregistry-server`` (PR #140).  Core cannot require
that release, so these tests skip when the installed server does not rebuild a
route on ``OVERRIDE``.
"""

from __future__ import annotations

import inspect

import pytest

from toolregistry import ToolRegistry

pytest.importorskip("toolregistry_server")

from toolregistry_server import RouteTable  # noqa: E402
from toolregistry_server.adapters.mcp._compat import (  # noqa: E402
    create_test_client,
    get_field,
)
from toolregistry_server.adapters.mcp.adapter import (  # noqa: E402
    route_table_to_mcp_server,
)


def _route_table_handles_override() -> bool:
    """Whether the installed server rebuilds a route on ``OVERRIDE``."""
    return "ChangeEventType.OVERRIDE" in inspect.getsource(
        RouteTable._on_registry_change
    )


pytestmark = pytest.mark.skipif(
    not _route_table_handles_override(),
    reason="toolregistry-server does not rebuild routes on OVERRIDE (PR #140)",
)


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def add_overridden(a: int, b: int) -> int:
    """Sum two numbers the local way."""
    return a + b + 1000


def _registry_with_override() -> tuple[ToolRegistry, object]:
    registry = ToolRegistry()
    registry.register(add)
    replacement = registry.override("add", add_overridden)
    return registry, replacement


def _reregister_and_reinstate(registry: ToolRegistry, replacement: object) -> None:
    """Do what the panel does: replace the source's tools, then restore."""
    with pytest.warns(UserWarning, match="recorded override was also discarded"):
        registry.register(add)
    assert registry._reinstate_override("add", replacement) is True


class TestRouteTableServesTheOverride:
    """A route must hold the reinstated tool, not the source's definition."""

    def test_route_holds_the_override_tool(self) -> None:
        registry, replacement = _registry_with_override()
        route_table = RouteTable(registry)
        route = route_table.get_route("add")
        assert route is not None
        assert route.tool is replacement

        _reregister_and_reinstate(registry, replacement)

        route = route_table.get_route("add")
        assert route is not None
        assert route.tool is registry.get_tool("add")
        assert route.tool is replacement
        assert route.description == "Sum two numbers the local way."
        assert route.handler(2, 3) == 1005


class TestMcpServesTheOverride:
    """An MCP client must see the override after the source re-registers."""

    @pytest.mark.asyncio
    async def test_tools_list_and_call_follow_the_override(self) -> None:
        registry, replacement = _registry_with_override()
        route_table = RouteTable(registry)
        # The SDK caches tools/list for its ttlMs; disable that so the
        # assertion reaches the server after the change event.
        server = route_table_to_mcp_server(route_table, list_tools_ttl_ms=0)

        async with create_test_client(server) as client:
            _reregister_and_reinstate(registry, replacement)

            listed = await client.list_tools()
            tool = next(t for t in listed.tools if t.name == "add")
            assert tool.description == "Sum two numbers the local way."

            result = await client.call_tool("add", {"a": 2, "b": 3})
            assert get_field(result, "is_error", "isError") is False
            assert result.content[0].text == "1005"
