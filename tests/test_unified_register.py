"""Tests for the unified register() and register_async() methods."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from toolregistry import ToolRegistry, Tool


# ------------------------------------------------------------------ #
#  Fixtures                                                           #
# ------------------------------------------------------------------ #


def sample_func(x: int) -> int:
    """Double a number."""
    return x * 2


class SampleClass:
    @staticmethod
    def add(a: int, b: int) -> int:
        return a + b

    @staticmethod
    def sub(a: int, b: int) -> int:
        return a - b


class InstanceClass:
    def greet(self, name: str) -> str:
        return f"Hello {name}"


# ------------------------------------------------------------------ #
#  Auto-detection: native                                             #
# ------------------------------------------------------------------ #


class TestAutoDetectNative:
    def test_register_function(self):
        reg = ToolRegistry()
        reg.register(sample_func)
        assert "sample_func" in reg._tools

    def test_register_tool_instance(self):
        reg = ToolRegistry()
        tool = Tool.from_function(sample_func, name="my_tool")
        reg.register(tool)
        assert "my_tool" in reg._tools

    def test_register_function_with_description(self):
        reg = ToolRegistry()
        reg.register(sample_func, description="custom desc", name="custom")
        assert "custom" in reg._tools
        assert reg._tools["custom"].description == "custom desc"

    def test_register_function_with_namespace(self):
        reg = ToolRegistry()
        reg.register(sample_func, namespace="ns")
        assert "ns-sample_func" in reg._tools

    def test_register_lambda(self):
        reg = ToolRegistry()
        reg.register(lambda x: x, name="identity")
        assert "identity" in reg._tools

    def test_register_callable_object(self):
        class Adder:
            def __call__(self, a: int, b: int) -> int:
                return a + b

        reg = ToolRegistry()
        reg.register(Adder(), name="adder")
        assert "adder" in reg._tools


# ------------------------------------------------------------------ #
#  Auto-detection: class                                              #
# ------------------------------------------------------------------ #


class TestAutoDetectClass:
    def test_register_class_type(self):
        reg = ToolRegistry()
        reg.register(SampleClass)
        names = list(reg._tools.keys())
        assert any("add" in n for n in names)
        assert any("sub" in n for n in names)

    def test_register_class_instance(self):
        reg = ToolRegistry()
        reg.register(InstanceClass())
        names = list(reg._tools.keys())
        assert any("greet" in n for n in names)

    def test_register_class_with_namespace(self):
        reg = ToolRegistry()
        reg.register(SampleClass, namespace="math")
        names = list(reg._tools.keys())
        assert any(n.startswith("math") for n in names)

    def test_register_class_with_traverse_mro_false(self):
        class Base:
            @staticmethod
            def base_method() -> str:
                return "base"

        class Child(Base):
            @staticmethod
            def child_method() -> str:
                return "child"

        reg = ToolRegistry()
        reg.register(Child, traverse_mro=False)
        names = list(reg._tools.keys())
        assert any("child_method" in n for n in names)
        assert not any("base_method" in n for n in names)


# ------------------------------------------------------------------ #
#  Explicit source                                                    #
# ------------------------------------------------------------------ #


class TestExplicitSource:
    def test_source_native(self):
        reg = ToolRegistry()
        reg.register(sample_func, source="native")
        assert "sample_func" in reg._tools

    def test_source_class(self):
        reg = ToolRegistry()
        reg.register(SampleClass, source="class")
        assert len(reg._tools) == 2

    def test_source_class_with_constructor_kwargs(self):
        class Configurable:
            def __init__(self, factor: int = 1):
                self.factor = factor

            def compute(self, x: int) -> int:
                return x * self.factor

        reg = ToolRegistry()
        reg.register(
            Configurable,
            source="class",
            constructor_kwargs={"factor": 3},
        )
        names = list(reg._tools.keys())
        assert any("compute" in n for n in names)


# ------------------------------------------------------------------ #
#  MCP source (mocked)                                                #
# ------------------------------------------------------------------ #


class TestMCPSource:
    def test_source_mcp_requires_explicit_source(self):
        reg = ToolRegistry()
        with pytest.raises(TypeError, match="Cannot auto-detect"):
            reg.register("http://localhost:8000/sse")

    @patch("toolregistry._mixins.registration._import_mcp_integration")
    def test_source_mcp_explicit(self, mock_import):
        mock_integration_cls = MagicMock()
        mock_import.return_value = mock_integration_cls
        mock_instance = mock_integration_cls.return_value

        reg = ToolRegistry()
        reg.register(
            "http://localhost:8000/sse",
            source="mcp",
            persistent=True,
            headers={"Authorization": "Bearer tok"},
        )

        mock_instance.register_mcp_tools.assert_called_once_with(
            "http://localhost:8000/sse",
            False,
            True,
            headers={"Authorization": "Bearer tok"},
        )
        assert mock_instance in reg._mcp_integrations


# ------------------------------------------------------------------ #
#  OpenAPI source (mocked)                                            #
# ------------------------------------------------------------------ #


class TestOpenAPISource:
    def test_openapi_missing_spec_raises(self):
        reg = ToolRegistry()
        with pytest.raises(TypeError, match="openapi_spec"):
            reg.register(MagicMock(), source="openapi")

    def test_callable_instance_detected_as_native(self):
        """Callable instances (__call__) go to native, not class."""

        class Adder:
            def __call__(self, a: int, b: int) -> int:
                return a + b

            def other_method(self):
                pass

        reg = ToolRegistry()
        reg.register(Adder(), name="adder")
        assert "adder" in reg._tools
        assert len(reg._tools) == 1

    @patch("toolregistry._mixins.registration._import_openapi_integration")
    def test_openapi_explicit(self, mock_import):
        mock_integration_cls = MagicMock()
        mock_import.return_value = mock_integration_cls
        mock_instance = mock_integration_cls.return_value

        client = MagicMock()
        spec = {"openapi": "3.0.0", "paths": {}}

        reg = ToolRegistry()
        reg.register(
            client,
            source="openapi",
            openapi_spec=spec,
            persistent=False,
            spec_url="https://example.com/openapi.json",
        )

        mock_instance.register_openapi_tools.assert_called_once_with(
            client, spec, False, False, spec_url="https://example.com/openapi.json"
        )
        assert mock_instance in reg._openapi_integrations


# ------------------------------------------------------------------ #
#  LangChain source (mocked)                                          #
# ------------------------------------------------------------------ #


class TestLangChainSource:
    @patch("toolregistry._mixins.registration._import_langchain_integration")
    def test_langchain_explicit(self, mock_import):
        mock_integration_cls = MagicMock()
        mock_import.return_value = mock_integration_cls

        mock_lc_tool = MagicMock()
        reg = ToolRegistry()
        reg.register(mock_lc_tool, source="langchain", namespace="lc")

        mock_integration_cls.return_value.register_langchain_tools.assert_called_once_with(
            mock_lc_tool, "lc"
        )


# ------------------------------------------------------------------ #
#  Error cases                                                        #
# ------------------------------------------------------------------ #


class TestErrors:
    def test_no_args_raises(self):
        reg = ToolRegistry()
        with pytest.raises(TypeError, match="missing required argument"):
            reg.register()

    def test_unknown_source_raises(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError, match="Unknown source"):
            reg.register(sample_func, source="redis")

    def test_string_without_source_raises(self):
        reg = ToolRegistry()
        with pytest.raises(TypeError, match="Cannot auto-detect"):
            reg.register("http://example.com")

    def test_dict_without_source_raises(self):
        reg = ToolRegistry()
        with pytest.raises(TypeError, match="Cannot auto-detect"):
            reg.register({"command": ["python", "server.py"]})

    def test_path_without_source_raises(self):
        from pathlib import Path

        reg = ToolRegistry()
        with pytest.raises(TypeError, match="Cannot auto-detect"):
            reg.register(Path("server.py"))

    def test_namespace_true_on_native_raises(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError, match="namespace=True is not supported"):
            reg.register(sample_func, namespace=True)


# ------------------------------------------------------------------ #
#  Async variants                                                     #
# ------------------------------------------------------------------ #


class TestRegisterAsync:
    @pytest.mark.asyncio
    async def test_async_native_function(self):
        reg = ToolRegistry()
        await reg.register_async(sample_func)
        assert "sample_func" in reg._tools

    @pytest.mark.asyncio
    async def test_async_class(self):
        reg = ToolRegistry()
        await reg.register_async(SampleClass, source="class")
        assert len(reg._tools) == 2

    @pytest.mark.asyncio
    async def test_async_no_args_raises(self):
        reg = ToolRegistry()
        with pytest.raises(TypeError, match="missing required argument"):
            await reg.register_async()

    @pytest.mark.asyncio
    async def test_async_unknown_source_raises(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError, match="Unknown source"):
            await reg.register_async(sample_func, source="redis")

    @pytest.mark.asyncio
    @patch("toolregistry._mixins.registration._import_mcp_integration")
    async def test_async_mcp(self, mock_import):
        mock_integration_cls = MagicMock()
        mock_import.return_value = mock_integration_cls
        mock_instance = mock_integration_cls.return_value
        mock_instance.register_mcp_tools_async = MagicMock(
            side_effect=lambda *a, **kw: asyncio.sleep(0)
        )

        reg = ToolRegistry()
        await reg.register_async(
            "http://localhost:8000",
            source="mcp",
        )
        mock_instance.register_mcp_tools_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_openapi_missing_spec(self):
        reg = ToolRegistry()
        with pytest.raises(TypeError, match="openapi_spec"):
            await reg.register_async(MagicMock(), source="openapi")


# ------------------------------------------------------------------ #
#  Backward compatibility                                             #
# ------------------------------------------------------------------ #


class TestBackwardCompat:
    def test_positional_description_and_name(self):
        """Old-style positional: register(func, "desc", "name")."""
        reg = ToolRegistry()
        reg.register(sample_func, "my desc", "my_name")
        assert "my_name" in reg._tools
        assert reg._tools["my_name"].description == "my desc"

    def test_keyword_description_and_name(self):
        """Keyword style: register(func, description=..., name=...)."""
        reg = ToolRegistry()
        reg.register(sample_func, description="kw desc", name="kw_name")
        assert "kw_name" in reg._tools
        assert reg._tools["kw_name"].description == "kw desc"

    def test_namespace_none_equals_false(self):
        """namespace=None and namespace=False should both mean no namespace."""
        reg1 = ToolRegistry()
        reg1.register(sample_func, namespace=None, name="t1")

        reg2 = ToolRegistry()
        reg2.register(sample_func, namespace=False, name="t2")

        assert "t1" in reg1._tools
        assert "t2" in reg2._tools

    def test_namespace_true_for_class(self):
        """namespace=True should derive namespace from class name."""
        reg = ToolRegistry()
        reg.register(SampleClass, namespace=True)
        names = list(reg._tools.keys())
        assert any("sample" in n.lower() for n in names)
