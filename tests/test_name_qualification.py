"""Tests for the shared tool-name qualification helper (#302)."""

from __future__ import annotations

import pytest

from toolregistry import ToolRegistry
from toolregistry._names import qualified_tool_name
from toolregistry.tool import Tool


def hello(x: int) -> int:
    """Say hello."""
    return x


class Calculator:
    """Minimal class tool source."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b


class TestQualifiedToolName:
    def test_namespace_with_hyphen(self):
        assert qualified_tool_name("hello", "math", "-") == "math-hello"

    def test_namespace_with_dot(self):
        assert qualified_tool_name("hello", "math", ".") == "math.hello"

    def test_no_namespace_normalizes(self):
        assert qualified_tool_name("getUserID", None, ".") == "get_user_id"

    def test_empty_namespace_normalizes(self):
        assert qualified_tool_name("getUserID", "", "-") == "get_user_id"

    def test_namespace_is_normalized(self):
        assert qualified_tool_name("hello", "Math Ops", ".") == "math_ops.hello"

    def test_raw_name_separator_characters_are_normalized(self):
        # qualified_tool_name takes a *raw* source name.  normalize_tool_name
        # turns dots and hyphens into underscores, so a raw name can never be
        # mistaken for an already-qualified one.
        assert qualified_tool_name("math.hello", None, ".") == "math_hello"
        assert qualified_tool_name("math-hello", "ns", ".") == "ns.math_hello"


class TestNativeRegistrationSeparator:
    def test_function_honours_dot_separator(self):
        registry = ToolRegistry(name_sep=".")
        registry.register(hello, namespace="math")
        assert set(registry._tools) == {"math.hello"}

    def test_function_default_separator_unchanged(self):
        registry = ToolRegistry()
        registry.register(hello, namespace="math")
        assert set(registry._tools) == {"math-hello"}

    def test_class_honours_dot_separator(self):
        registry = ToolRegistry(name_sep=".")
        registry.register(Calculator, source="class", namespace="math")
        assert set(registry._tools) == {"math.add"}

    def test_class_default_separator_unchanged(self):
        registry = ToolRegistry()
        registry.register(Calculator, source="class", namespace="math")
        assert set(registry._tools) == {"math-add"}

    def test_from_function_accepts_separator(self):
        tool = Tool.from_function(hello, namespace="math", sep=".")
        assert tool.name == "math.hello"
        assert tool.namespace == "math"
        assert tool.method_name == "hello"

    def test_registry_exposes_separator(self):
        assert ToolRegistry().name_sep == "-"
        assert ToolRegistry(name_sep=".").name_sep == "."


class TestSeparatorSetter:
    def test_accepts_supported_values(self):
        registry = ToolRegistry()
        registry.name_sep = "."
        assert registry.name_sep == "."

    def test_rejects_other_values(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError, match=r"'-' or '\.'"):
            registry.name_sep = "_"


class TestRegistryKeyContract:
    """qualified_tool_name must predict the key registration stores."""

    @pytest.mark.parametrize("sep", ["-", "."])
    @pytest.mark.parametrize("namespace", [None, "math_ops", "Math Ops"])
    @pytest.mark.parametrize(
        "raw_name", ["hello", "getUserID", "get user info", "list.issues"]
    )
    def test_predicted_name_is_the_registered_key(self, sep, namespace, raw_name):
        registry = ToolRegistry(name_sep=sep)
        registry.register(hello, name=raw_name, namespace=namespace)

        assert set(registry._tools) == {qualified_tool_name(raw_name, namespace, sep)}
