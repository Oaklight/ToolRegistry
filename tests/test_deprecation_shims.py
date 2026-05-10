"""Tests for backward-compatibility deprecation shims.

Verifies that importing from old paths (toolregistry.mcp, etc.)
emits DeprecationWarning and re-exports the correct symbols.
"""

import importlib
import warnings

import pytest


def _import_with_warning(module_path: str):
    """Import a module and assert it emits a DeprecationWarning."""
    # Remove cached shim modules so the warning fires again
    import sys

    for key in list(sys.modules):
        if key.startswith(module_path):
            del sys.modules[key]

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        mod = importlib.import_module(module_path)
        deprecation_warnings = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) >= 1, (
            f"Expected DeprecationWarning from {module_path}, got none"
        )
        assert "deprecated" in str(deprecation_warnings[0].message).lower()
    return mod


# ---------------------------------------------------------------------------
# Native shims (no optional dependency)
# ---------------------------------------------------------------------------


class TestNativeShims:
    def test_native_init(self):
        mod = _import_with_warning("toolregistry.native")
        from toolregistry.integrations.native import ClassToolIntegration

        assert mod.ClassToolIntegration is ClassToolIntegration

    def test_native_integration(self):
        mod = _import_with_warning("toolregistry.native.integration")
        from toolregistry.integrations.native.integration import ClassToolIntegration

        assert mod.ClassToolIntegration is ClassToolIntegration

    def test_native_utils(self):
        mod = _import_with_warning("toolregistry.native.utils")
        from toolregistry.integrations.native.utils import (
            _determine_namespace,
            _is_all_static_methods,
            get_all_static_methods,
        )

        assert mod._determine_namespace is _determine_namespace
        assert mod._is_all_static_methods is _is_all_static_methods
        assert mod.get_all_static_methods is get_all_static_methods


# ---------------------------------------------------------------------------
# MCP shims (requires mcp extra)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not pytest.importorskip("mcp", reason="mcp extra not installed"),
    reason="mcp extra not installed",
)
class TestMCPShims:
    def test_mcp_init(self):
        mod = _import_with_warning("toolregistry.mcp")
        from toolregistry.integrations.mcp import MCPIntegration

        assert mod.MCPIntegration is MCPIntegration

    def test_mcp_client(self):
        mod = _import_with_warning("toolregistry.mcp.client")
        from toolregistry.integrations.mcp.client import MCPClient

        assert mod.MCPClient is MCPClient

    def test_mcp_integration(self):
        mod = _import_with_warning("toolregistry.mcp.integration")
        from toolregistry.integrations.mcp.integration import MCPTool

        assert mod.MCPTool is MCPTool

    def test_mcp_connection(self):
        mod = _import_with_warning("toolregistry.mcp.connection")
        from toolregistry.integrations.mcp.connection import MCPConnectionManager

        assert mod.MCPConnectionManager is MCPConnectionManager


# ---------------------------------------------------------------------------
# OpenAPI shims (requires openapi extra)
# ---------------------------------------------------------------------------


class TestOpenAPIShims:
    def test_openapi_init(self):
        mod = _import_with_warning("toolregistry.openapi")
        from toolregistry.integrations.openapi import OpenAPIIntegration

        assert mod.OpenAPIIntegration is OpenAPIIntegration

    def test_openapi_integration(self):
        mod = _import_with_warning("toolregistry.openapi.integration")
        from toolregistry.integrations.openapi.integration import OpenAPIToolWrapper

        assert mod.OpenAPIToolWrapper is OpenAPIToolWrapper

    def test_openapi_utils(self):
        mod = _import_with_warning("toolregistry.openapi.utils")
        from toolregistry.integrations.openapi.utils import load_openapi_spec

        assert mod.load_openapi_spec is load_openapi_spec


# ---------------------------------------------------------------------------
# LangChain shims (requires langchain extra)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not pytest.importorskip("langchain_core", reason="langchain extra not installed"),
    reason="langchain extra not installed",
)
class TestLangChainShims:
    def test_langchain_init(self):
        mod = _import_with_warning("toolregistry.langchain")
        from toolregistry.integrations.langchain import LangChainIntegration

        assert mod.LangChainIntegration is LangChainIntegration

    def test_langchain_integration(self):
        mod = _import_with_warning("toolregistry.langchain.integration")
        from toolregistry.integrations.langchain.integration import LangChainToolWrapper

        assert mod.LangChainToolWrapper is LangChainToolWrapper
