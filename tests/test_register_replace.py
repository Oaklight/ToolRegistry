"""Tests for replacement visibility on plain registration (#290).

A registration that lands on an existing name must not be silent: it emits
a ``UserWarning`` by default and a ``REPLACE`` change event, while
``allow_replace=True`` acknowledges the replacement and suppresses only
the warning.  Last-write-wins replacement semantics are unchanged.
"""

from __future__ import annotations

import warnings
from unittest.mock import AsyncMock, patch

import pytest

from toolregistry import ToolRegistry
from toolregistry.events import ChangeEventType
from toolregistry.tool import Tool
from toolregistry.utils import HttpClientConfig

try:
    from toolregistry.integrations.mcp.integration import MCPIntegration

    _HAS_MCP = True
except ImportError:  # pragma: no cover - depends on the mcp extra
    MCPIntegration = None  # type: ignore[assignment]
    _HAS_MCP = False

requires_mcp = pytest.mark.skipif(not _HAS_MCP, reason="mcp extra not installed")


def _add_one() -> int:
    """Return one."""
    return 1


def _add_two() -> int:
    """Return two."""
    return 2


def _replacement_warnings(caught):
    return [w for w in caught if "already registered" in str(w.message)]


class _MockToolSpec:
    """Minimal stand-in for ``mcp.types.Tool``."""

    def __init__(self, name):
        self.name = name
        self.description = ""
        self.input_schema = {"type": "object", "properties": {}}


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


# ---------------------------------------------------------------------------
# Native registration
# ---------------------------------------------------------------------------


class TestNativeReplacement:
    def test_register_onto_existing_name_warns(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="dup")

        with pytest.warns(UserWarning, match="already registered"):
            reg.register(_add_two, name="dup")

        assert reg.invoke("dup", {}).result == "2"

    def test_allow_replace_suppresses_warning(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="dup")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            reg.register(_add_two, name="dup", allow_replace=True)

        assert not _replacement_warnings(caught)
        assert reg.invoke("dup", {}).result == "2"

    def test_allow_replace_without_collision_is_silent(self):
        reg = ToolRegistry()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            reg.register(_add_one, name="fresh", allow_replace=True)
        assert not _replacement_warnings(caught)
        assert "fresh" in reg._tools

    def test_replace_event_is_emitted(self):
        reg = ToolRegistry()
        events = []
        reg.on_change(events.append)
        reg.register(_add_one, name="dup")
        events.clear()

        reg.register(_add_two, name="dup", allow_replace=True)

        assert [event.event_type for event in events] == [
            ChangeEventType.REGISTER,
            ChangeEventType.REPLACE,
        ]
        replaced = events[-1]
        assert replaced.tool_name == "dup"
        assert replaced.metadata["replaced_tool"] is not None

    def test_warning_as_error_still_runs_hooks_and_emits_events(self):
        """A warning configured as an error must not skip observable work."""
        reg = ToolRegistry()
        reg.register(_add_one, name="dup")
        events = []
        hooks: list[str] = []
        reg.on_change(events.append)
        reg.add_post_register_hook(lambda name, tool, registry: hooks.append(name))
        events.clear()

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(UserWarning, match="already registered"):
                reg.register(_add_two, name="dup")

        # The swap happened before the warning, so listeners and hooks must
        # have observed it even though the warning aborted the call.
        assert reg.invoke("dup", {}).result == "2"
        assert [event.event_type for event in events] == [
            ChangeEventType.REGISTER,
            ChangeEventType.REPLACE,
        ]
        assert hooks == ["dup"]

    def test_replacement_warning_points_at_caller_frame(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="dup")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            reg.register(_add_two, name="dup")

        matches = _replacement_warnings(caught)
        assert len(matches) == 1
        assert matches[0].filename == __file__

    def test_no_replace_event_without_replacement(self):
        reg = ToolRegistry()
        events = []
        reg.on_change(events.append)

        reg.register(_add_one, name="fresh")

        assert [event.event_type for event in events] == [ChangeEventType.REGISTER]

    def test_reregistering_same_tool_object_is_not_a_replacement(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="dup")
        tool = reg._tools["dup"]

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            reg.register(tool)

        assert not _replacement_warnings(caught)

    def test_reregistering_same_tool_object_with_namespace_is_not_a_replacement(self):
        reg = ToolRegistry()
        tool = Tool.from_function(_add_one, name="dup")
        reg.register(tool, namespace="ns")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            reg.register(tool, namespace="ns")

        assert not _replacement_warnings(caught)

    def test_replacement_drops_override_record_and_mentions_it(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="dup")
        reg.override("dup", _add_two)

        with pytest.warns(UserWarning, match="recorded override was also discarded"):
            reg.register(lambda: 3, name="dup")

        assert reg.list_overrides() == {}

    @pytest.mark.asyncio
    async def test_async_allow_replace(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="dup")

        await reg.register_async(_add_two, name="dup", allow_replace=True)

        assert reg.invoke("dup", {}).result == "2"


# ---------------------------------------------------------------------------
# Class source
# ---------------------------------------------------------------------------


class TestClassReplacement:
    class First:
        def greet(self) -> str:
            return "first"

    class Second:
        def greet(self) -> str:
            return "second"

    def test_class_registration_warns(self):
        reg = ToolRegistry()
        reg.register(self.First, source="class")

        with pytest.warns(UserWarning, match="already registered"):
            reg.register(self.Second, source="class")

        assert reg.invoke("greet", {}).result == "second"

    def test_class_registration_allow_replace(self):
        reg = ToolRegistry()
        reg.register(self.First, source="class")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            reg.register(self.Second, source="class", allow_replace=True)

        assert not _replacement_warnings(caught)
        assert reg.invoke("greet", {}).result == "second"


# ---------------------------------------------------------------------------
# Remote sources
# ---------------------------------------------------------------------------


@requires_mcp
class TestMCPReplacement:
    def test_mcp_collision_warns(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="add")
        before = reg._tools["add"]
        integration = MCPIntegration(reg)

        with _patch_mcp_client([_MockToolSpec("add")]):
            with pytest.warns(UserWarning, match="already registered"):
                integration.register_mcp_tools("http://mock-mcp:8000")

        assert reg._tools["add"] is not before

    def test_mcp_allow_replace(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="add")
        integration = MCPIntegration(reg)

        with _patch_mcp_client([_MockToolSpec("add")]):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                integration.register_mcp_tools(
                    "http://mock-mcp:8000", allow_replace=True
                )

        assert not _replacement_warnings(caught)


class TestOpenAPIReplacement:
    def _register(self, registry, **kwargs):
        registry.register(
            HttpClientConfig(base_url="http://test.example.com"),
            source="openapi",
            openapi_spec=OPENAPI_SPEC,
            **kwargs,
        )

    def test_openapi_collision_warns(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="list_items")

        with pytest.warns(UserWarning, match="already registered"):
            self._register(reg)

    def test_openapi_allow_replace(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="list_items")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self._register(reg, allow_replace=True)

        assert not _replacement_warnings(caught)


class TestLangChainReplacement:
    def _tool(self):
        pytest.importorskip("langchain_core")
        from tests.test_langchain_integration import MockAddTool

        return MockAddTool()

    def test_langchain_collision_warns(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="add_numbers")

        with pytest.warns(UserWarning, match="already registered"):
            reg.register(self._tool(), source="langchain")

    def test_langchain_allow_replace(self):
        reg = ToolRegistry()
        reg.register(_add_one, name="add_numbers")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            reg.register(self._tool(), source="langchain", allow_replace=True)

        assert not _replacement_warnings(caught)
