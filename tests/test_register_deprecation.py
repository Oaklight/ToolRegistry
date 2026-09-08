"""Tests for deprecated register_from_* aliases."""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock, patch

import pytest

from toolregistry import ToolRegistry


class SampleClass:
    @staticmethod
    def add(a: int, b: int) -> int:
        return a + b


# ------------------------------------------------------------------ #
#  Sync deprecation warnings                                          #
# ------------------------------------------------------------------ #


class TestDeprecationWarnings:
    def test_register_from_class_warns(self):
        reg = ToolRegistry()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            reg.register_from_class(SampleClass)
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1
        assert "register_from_class" in str(dep_warnings[0].message)
        assert "register(" in str(dep_warnings[0].message)

    def test_register_from_class_still_works(self):
        reg = ToolRegistry()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            reg.register_from_class(SampleClass)
        assert any("add" in n for n in reg._tools)

    @patch("toolregistry._mixins.registration._import_mcp_integration")
    def test_register_from_mcp_warns(self, mock_import):
        mock_import.return_value = MagicMock()
        reg = ToolRegistry()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            reg.register_from_mcp("http://localhost:8000")
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1
        assert "register_from_mcp" in str(dep_warnings[0].message)

    @patch("toolregistry._mixins.registration._import_openapi_integration")
    def test_register_from_openapi_warns(self, mock_import):
        mock_import.return_value = MagicMock()
        reg = ToolRegistry()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            reg.register_from_openapi(
                MagicMock(),
                {"openapi": "3.0.0", "paths": {}},
            )
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1
        assert "register_from_openapi" in str(dep_warnings[0].message)

    @patch("toolregistry._mixins.registration._import_langchain_integration")
    def test_register_from_langchain_warns(self, mock_import):
        mock_import.return_value = MagicMock()
        reg = ToolRegistry()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            reg.register_from_langchain(MagicMock())
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1
        assert "register_from_langchain" in str(dep_warnings[0].message)


# ------------------------------------------------------------------ #
#  Async deprecation warnings                                        #
# ------------------------------------------------------------------ #


class TestAsyncDeprecationWarnings:
    @pytest.mark.asyncio
    async def test_register_from_class_async_warns(self):
        reg = ToolRegistry()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await reg.register_from_class_async(SampleClass)
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1
        assert "register_from_class_async" in str(dep_warnings[0].message)

    @pytest.mark.asyncio
    async def test_register_from_class_async_still_works(self):
        reg = ToolRegistry()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            await reg.register_from_class_async(SampleClass)
        assert any("add" in n for n in reg._tools)
