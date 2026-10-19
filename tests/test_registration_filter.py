"""Tests for the registration-time include/exclude filter (#281).

Covers the shared ``ToolNameFilter`` helper, the MCP / OpenAPI / LangChain
registration paths that apply it, refresh behavior, and the argument
validation performed by the unified ``register()`` entry point.
"""

from __future__ import annotations

import warnings
from unittest.mock import AsyncMock, patch

import pytest

from toolregistry import ToolRegistry
from toolregistry.utils import HttpClientConfig, ToolNameFilter

try:
    from toolregistry.integrations.mcp.integration import MCPIntegration

    _HAS_MCP = True
except ImportError:  # pragma: no cover - depends on the mcp extra
    MCPIntegration = None  # type: ignore[assignment]
    _HAS_MCP = False

requires_mcp = pytest.mark.skipif(not _HAS_MCP, reason="mcp extra not installed")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _MockToolSpec:
    """Minimal stand-in for ``mcp.types.Tool``."""

    def __init__(self, name, description="", input_schema=None):
        self.name = name
        self.description = description
        self.input_schema = input_schema or {"type": "object", "properties": {}}


def _patch_mcp_client(tool_specs):
    """Patch ``MCPClient`` so ``list_tools()`` returns *tool_specs*."""
    mock_client = AsyncMock()
    mock_client.server_info = None
    mock_client.list_tools = AsyncMock(return_value=tool_specs)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "toolregistry.integrations.mcp.integration.MCPClient",
        return_value=mock_client,
    )


def _lc_mocks():
    """Return the LangChain mock tool classes, skipping when unavailable."""
    pytest.importorskip("langchain_core")
    from tests.test_langchain_integration import MockAddTool, MockUpperTool

    return MockAddTool, MockUpperTool


OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "TestAPI", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {"operationId": "listItems", "summary": "List items"},
        },
        "/admin": {
            "post": {"operationId": "adminDelete", "summary": "Delete everything"},
        },
    },
}


# ---------------------------------------------------------------------------
# ToolNameFilter (unit)
# ---------------------------------------------------------------------------


class TestToolNameFilter:
    def test_none_accepts_everything(self):
        f = ToolNameFilter()
        assert f.accepts("add", "svc-add") is True

    def test_include_exact_raw_name(self):
        f = ToolNameFilter(include=["add"])
        assert f.accepts("add", "svc-add") is True
        assert f.accepts("multiply", "svc-multiply") is False

    def test_include_matches_post_namespace_name(self):
        f = ToolNameFilter(include=["svc-*"])
        assert f.accepts("add", "svc-add") is True
        assert f.accepts("add", "other-add") is False

    def test_exclude_glob(self):
        f = ToolNameFilter(exclude=["*_admin_*"])
        assert f.accepts("user_admin_delete", "user_admin_delete") is False
        assert f.accepts("list_issues", "list_issues") is True

    def test_empty_include_drops_everything(self):
        f = ToolNameFilter(include=[])
        assert f.accepts("add", "add") is False

    def test_bare_string_is_a_single_pattern(self):
        f = ToolNameFilter(include="add")
        assert f.accepts("add", "svc-add") is True
        assert f.accepts("a", "svc-a") is False

    def test_bare_string_glob_is_a_single_pattern(self):
        f = ToolNameFilter(exclude="admin_*")
        assert f.accepts("admin_delete", "admin_delete") is False
        assert f.accepts("list_issues", "list_issues") is True

    def test_normalized_unprefixed_name_matches(self):
        f = ToolNameFilter(include=["bash_execute"])
        assert f.accepts("bash-execute", "hub-bash_execute") is True

    def test_normalized_namespaced_name_matches(self):
        f = ToolNameFilter(include=["hub_bash_execute"])
        assert f.accepts("bash-execute", "hub-bash_execute") is True

    def test_exclude_matches_normalized_spelling(self):
        f = ToolNameFilter(exclude=["bash_execute"])
        assert f.accepts("bash-execute", "hub-bash_execute") is False

    def test_both_sides_raise(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            ToolNameFilter(include=["a"], exclude=["b"])

    def test_warn_if_all_filtered_out_inactive_filter_is_silent(self):
        f = ToolNameFilter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            f.warn_if_all_filtered_out(total=3, accepted=0, source="MCP")
        assert not [w for w in caught if "nothing was registered" in str(w.message)]

    def test_warn_if_all_filtered_out_is_silent_when_something_registered(self):
        f = ToolNameFilter(include=["add"])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            f.warn_if_all_filtered_out(total=3, accepted=1, source="MCP")
        assert not [w for w in caught if "nothing was registered" in str(w.message)]

    def test_warn_if_all_filtered_out_warns_for_empty_include(self):
        f = ToolNameFilter(include=[])
        with pytest.warns(UserWarning, match=r"include=\[\] matched none of 3"):
            f.warn_if_all_filtered_out(total=3, accepted=0, source="MCP")

    def test_warn_if_all_filtered_out_warns_for_exclude_all(self):
        f = ToolNameFilter(exclude=["upper_*"])
        with pytest.warns(UserWarning, match=r"excluded all 3 tool"):
            f.warn_if_all_filtered_out(total=3, accepted=0, source="MCP")


# ---------------------------------------------------------------------------
# MCP registration filter
# ---------------------------------------------------------------------------


@requires_mcp
class TestMCPRegistrationFilter:
    @pytest.mark.asyncio
    async def test_include_list(self):
        specs = [
            _MockToolSpec("add"),
            _MockToolSpec("multiply"),
            _MockToolSpec("subtract"),
        ]
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with _patch_mcp_client(specs):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", include=["add"]
            )
        assert set(registry._tools) == {"add"}

    @pytest.mark.asyncio
    async def test_exclude_glob(self):
        specs = [
            _MockToolSpec("list_issues"),
            _MockToolSpec("admin_delete"),
            _MockToolSpec("admin_reset"),
        ]
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with _patch_mcp_client(specs):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", exclude=["admin_*"]
            )
        assert set(registry._tools) == {"list_issues"}

    @pytest.mark.asyncio
    async def test_pattern_matches_namespaced_name(self):
        specs = [_MockToolSpec("list_issues"), _MockToolSpec("get_issue")]
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with _patch_mcp_client(specs):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", namespace="gh", include=["gh-list_*"]
            )
        assert set(registry._tools) == {"gh-list_issues"}

    @pytest.mark.asyncio
    async def test_bare_string_include(self):
        specs = [_MockToolSpec("add"), _MockToolSpec("multiply")]
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with _patch_mcp_client(specs):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", include="add"
            )
        assert set(registry._tools) == {"add"}

    @pytest.mark.asyncio
    async def test_normalized_spelling_include(self):
        specs = [_MockToolSpec("bash-execute")]
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with _patch_mcp_client(specs):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", namespace="hub", include=["bash_execute"]
            )
        assert set(registry._tools) == {"hub-bash_execute"}

    @pytest.mark.asyncio
    async def test_filter_matching_nothing_warns(self):
        specs = [_MockToolSpec("add"), _MockToolSpec("multiply")]
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with (
            _patch_mcp_client(specs),
            pytest.warns(UserWarning, match="matched none of 2"),
        ):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", include=["no_such_tool"]
            )
        assert registry._tools == {}

    @pytest.mark.asyncio
    async def test_empty_include_warns(self):
        specs = [_MockToolSpec("add")]
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with _patch_mcp_client(specs), pytest.warns(UserWarning, match=r"include=\[\]"):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", include=[]
            )
        assert registry._tools == {}

    @pytest.mark.asyncio
    async def test_exclude_all_warns(self):
        specs = [_MockToolSpec("add"), _MockToolSpec("multiply")]
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with (
            _patch_mcp_client(specs),
            pytest.warns(UserWarning, match=r"excluded all 2 tool"),
        ):
            await integration.register_mcp_tools_async(
                "http://mock-mcp:8000", exclude=["*"]
            )
        assert registry._tools == {}

    @pytest.mark.asyncio
    async def test_matching_filter_does_not_warn(self):
        specs = [_MockToolSpec("add"), _MockToolSpec("multiply")]
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with _patch_mcp_client(specs):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                await integration.register_mcp_tools_async(
                    "http://mock-mcp:8000", include=["add"]
                )
        assert not [w for w in caught if "matched none" in str(w.message)]

    @pytest.mark.asyncio
    async def test_unfiltered_empty_server_does_not_warn(self):
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with _patch_mcp_client([]):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                await integration.register_mcp_tools_async("http://mock-mcp:8000")
        assert not [w for w in caught if "matched none" in str(w.message)]

    def test_refresh_does_not_resurrect_excluded(self):
        specs = [_MockToolSpec("add"), _MockToolSpec("multiply")]
        registry = ToolRegistry()
        integration = MCPIntegration(registry)
        with _patch_mcp_client(specs):
            integration.register_mcp_tools("http://mock-mcp:8000", include=["add"])
        assert set(registry._tools) == {"add"}

        with _patch_mcp_client(specs):
            result = integration.refresh()

        assert "multiply" not in registry._tools
        assert "multiply" not in result.added
        assert "multiply" not in result.removed
        assert result.unchanged == 1


# ---------------------------------------------------------------------------
# OpenAPI registration filter
# ---------------------------------------------------------------------------


class TestOpenAPIRegistrationFilter:
    def _register(self, registry, **kwargs):
        registry.register(
            HttpClientConfig(base_url="http://test.example.com"),
            source="openapi",
            openapi_spec=OPENAPI_SPEC,
            **kwargs,
        )

    def test_exclude_glob(self):
        registry = ToolRegistry()
        self._register(registry, exclude=["admin_*"])
        assert set(registry._tools) == {"list_items"}

    def test_include_list(self):
        registry = ToolRegistry()
        self._register(registry, include=["listItems"])
        assert set(registry._tools) == {"list_items"}

    def test_bare_string_include(self):
        registry = ToolRegistry()
        self._register(registry, include="listItems")
        assert set(registry._tools) == {"list_items"}

    def test_normalized_spelling_include(self):
        registry = ToolRegistry()
        self._register(registry, namespace="api", include=["api_list_items"])
        assert set(registry._tools) == {"api-list_items"}

    def test_filter_matching_nothing_warns(self):
        registry = ToolRegistry()
        with pytest.warns(UserWarning, match="matched none of 2"):
            self._register(registry, include=["no_such_tool"])
        assert registry._tools == {}

    def test_refresh_does_not_resurrect_excluded(self):
        registry = ToolRegistry()
        self._register(registry, exclude=["admin_*"])

        result = registry.refresh_from_openapi(openapi_spec=OPENAPI_SPEC)

        assert "admin_delete" not in registry._tools
        assert "admin_delete" not in result.added
        assert "admin_delete" not in result.removed


# ---------------------------------------------------------------------------
# LangChain registration filter
# ---------------------------------------------------------------------------


class TestLangChainRegistrationFilter:
    def test_include_list_keeps_match(self):
        mock_add, _ = _lc_mocks()
        registry = ToolRegistry()
        registry.register(mock_add(), source="langchain", include=["add_numbers"])
        assert set(registry._tools) == {"add_numbers"}

    def test_exclude_glob_drops_match(self):
        _, mock_upper = _lc_mocks()
        registry = ToolRegistry()
        registry.register(mock_upper(), source="langchain", exclude=["upper_*"])
        assert registry._tools == {}

    def test_bare_string_include(self):
        mock_add, _ = _lc_mocks()
        registry = ToolRegistry()
        registry.register(mock_add(), source="langchain", include="add_numbers")
        assert set(registry._tools) == {"add_numbers"}

    def test_single_tool_source_does_not_warn(self):
        """One tool per call is not evidence of a misconfigured source."""
        mock_add, _ = _lc_mocks()
        registry = ToolRegistry()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            registry.register(mock_add(), source="langchain", include=["no_such_tool"])
        assert registry._tools == {}
        assert not [w for w in caught if "nothing was registered" in str(w.message)]

    @pytest.mark.asyncio
    async def test_async_exclude(self):
        _, mock_upper = _lc_mocks()
        registry = ToolRegistry()
        await registry.register_async(
            mock_upper(), source="langchain", exclude=["upper_*"]
        )
        assert registry._tools == {}


# ---------------------------------------------------------------------------
# Argument validation via unified register()
# ---------------------------------------------------------------------------


class TestFilterValidation:
    def test_both_include_and_exclude_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="mutually exclusive"):
            registry.register(lambda x: x, include=["a"], exclude=["b"])

    def test_filter_on_native_source_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="not supported for source='native'"):
            registry.register(lambda x: x, include=["a"])

    def test_filter_on_class_source_raises(self):
        class Foo:
            def bar(self) -> int:
                return 1

        registry = ToolRegistry()
        with pytest.raises(ValueError, match="not supported for source='class'"):
            registry.register(Foo, source="class", exclude=["bar"])

    def test_filter_on_mcp_source_with_both_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="mutually exclusive"):
            registry.register(
                "http://mock-mcp:8000",
                source="mcp",
                include=["a"],
                exclude=["b"],
            )

    @pytest.mark.asyncio
    async def test_async_filter_on_native_source_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="not supported for source='native'"):
            await registry.register_async(lambda x: x, exclude=["a"])
