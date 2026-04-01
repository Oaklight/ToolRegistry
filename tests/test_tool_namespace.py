"""Tests for Tool namespace and method_name fields (Issue #51)."""

from toolregistry.tool import Tool
from toolregistry.tool_registry import ToolRegistry


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


def dummy_add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def dummy_subtract(a: int, b: int) -> int:
    """Subtract b from a."""
    return a - b


class Calculator:
    @staticmethod
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @staticmethod
    def subtract(a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b


class Greeter:
    def hello(self, name: str) -> str:
        """Say hello."""
        return f"Hello, {name}!"

    def goodbye(self, name: str) -> str:
        """Say goodbye."""
        return f"Goodbye, {name}!"


# ===========================================================================
# 1. Tool creation – namespace and method_name defaults
# ===========================================================================


class TestToolFieldDefaults:
    """Verify that namespace and method_name default to None on plain Tool."""

    def test_defaults_are_none(self):
        tool = Tool.from_function(dummy_add)
        assert tool.namespace is None
        # method_name should be set to the normalized function name
        assert tool.method_name == "dummy_add"

    def test_name_unchanged_without_namespace(self):
        tool = Tool.from_function(dummy_add)
        assert tool.name == "dummy_add"


# ===========================================================================
# 2. from_function() with namespace / method_name
# ===========================================================================


class TestFromFunctionWithNamespace:
    """Test Tool.from_function() when namespace and method_name are provided."""

    def test_namespace_sets_fields(self):
        tool = Tool.from_function(dummy_add, namespace="calc")
        assert tool.namespace == "calc"
        assert tool.method_name == "dummy_add"
        assert tool.name == "calc-dummy_add"

    def test_method_name_override(self):
        tool = Tool.from_function(dummy_add, namespace="calc", method_name="my_add")
        assert tool.method_name == "my_add"
        # name is built from the function name, then namespace is prepended
        assert tool.name == "calc-dummy_add"

    def test_namespace_normalized(self):
        tool = Tool.from_function(dummy_add, namespace="MyCalc")
        assert tool.namespace == "my_calc"
        assert tool.name == "my_calc-dummy_add"

    def test_no_namespace(self):
        tool = Tool.from_function(dummy_add)
        assert tool.namespace is None
        assert tool.name == "dummy_add"


# ===========================================================================
# 3. update_namespace() maintains namespace / method_name
# ===========================================================================


class TestUpdateNamespace:
    """Test that update_namespace() correctly sets namespace and method_name."""

    def test_update_sets_namespace_field(self):
        tool = Tool.from_function(dummy_add)
        tool.update_namespace("math")
        assert tool.namespace == "math"
        assert tool.method_name == "dummy_add"
        assert tool.name == "math-dummy_add"

    def test_update_force_replaces_namespace(self):
        tool = Tool.from_function(dummy_add, namespace="old")
        assert tool.namespace == "old"
        tool.update_namespace("new", force=True)
        assert tool.namespace == "new"
        assert tool.name == "new-dummy_add"

    def test_update_no_force_keeps_existing(self):
        tool = Tool.from_function(dummy_add, namespace="old")
        tool.update_namespace("new", force=False)
        # namespace field is updated, but name is NOT changed
        assert tool.namespace == "new"
        assert tool.name == "old-dummy_add"

    def test_update_derives_method_name_from_prefixed_name(self):
        """If method_name was not set, update_namespace derives it from name."""
        tool = Tool(
            name="ns-some_func",
            description="test",
            parameters={},
            callable=dummy_add,
        )
        assert tool.method_name is None
        tool.update_namespace("new_ns", force=True)
        assert tool.method_name == "some_func"
        assert tool.namespace == "new_ns"

    def test_update_derives_method_name_from_plain_name(self):
        """If method_name was not set and name has no separator."""
        tool = Tool(
            name="some_func",
            description="test",
            parameters={},
            callable=dummy_add,
        )
        tool.update_namespace("ns")
        assert tool.method_name == "some_func"
        assert tool.namespace == "ns"
        assert tool.name == "ns-some_func"


# ===========================================================================
# 4. qualified_name property
# ===========================================================================


class TestQualifiedName:
    """Test the qualified_name property."""

    def test_with_namespace_and_method_name(self):
        tool = Tool.from_function(dummy_add, namespace="calc")
        assert tool.qualified_name == "calc-dummy_add"

    def test_without_namespace(self):
        tool = Tool.from_function(dummy_add)
        assert tool.qualified_name == "dummy_add"

    def test_qualified_name_matches_name_when_namespace_set(self):
        tool = Tool.from_function(dummy_add, namespace="calc")
        assert tool.qualified_name == tool.name


# ===========================================================================
# 5. _update_sub_registries uses namespace field
# ===========================================================================


class TestUpdateSubRegistries:
    """Test that _update_sub_registries uses the namespace field."""

    def test_groups_by_namespace_field(self):
        registry = ToolRegistry(name="test")
        registry.register(dummy_add, namespace="math")
        registry.register(dummy_subtract, namespace="math")
        registry._update_sub_registries()
        assert "math" in registry._sub_registries

    def test_fallback_to_dot_prefix(self):
        """Tools without namespace field fall back to dot-prefix parsing."""
        registry = ToolRegistry(name="test")
        # Manually insert a tool with dot-separated name but no namespace
        tool = Tool(
            name="legacy.some_func",
            description="test",
            parameters={},
            callable=dummy_add,
        )
        registry._tools["legacy.some_func"] = tool
        registry._update_sub_registries()
        assert "legacy" in registry._sub_registries

    def test_namespace_field_preferred_over_dot(self):
        """When namespace field is set, it takes priority."""
        registry = ToolRegistry(name="test")
        tool = Tool(
            name="wrong_prefix.some_func",
            description="test",
            parameters={},
            callable=dummy_add,
            namespace="correct_ns",
            method_name="some_func",
        )
        registry._tools["wrong_prefix.some_func"] = tool
        registry._update_sub_registries()
        assert "correct_ns" in registry._sub_registries
        # The dot-prefix "wrong_prefix" should NOT appear since namespace is set
        assert "wrong_prefix" not in registry._sub_registries


# ===========================================================================
# 6. register_from_class sets namespace / method_name
# ===========================================================================


class TestRegisterFromClass:
    """Test that register_from_class correctly sets namespace and method_name."""

    def test_static_class_with_namespace(self):
        registry = ToolRegistry(name="test")
        registry.register_from_class(Calculator, namespace=True)
        tools = registry.list_tools()
        assert len(tools) == 2

        for tool_name in tools:
            tool = registry.get_tool(tool_name)
            assert tool is not None
            assert tool.namespace == "calculator"
            assert tool.method_name in ("add", "subtract")

    def test_static_class_with_custom_namespace(self):
        registry = ToolRegistry(name="test")
        registry.register_from_class(Calculator, namespace="math")
        tools = registry.list_tools()

        for tool_name in tools:
            tool = registry.get_tool(tool_name)
            assert tool is not None
            assert tool.namespace == "math"

    def test_static_class_without_namespace(self):
        registry = ToolRegistry(name="test")
        registry.register_from_class(Calculator, namespace=False)
        tools = registry.list_tools()

        for tool_name in tools:
            tool = registry.get_tool(tool_name)
            assert tool is not None
            assert tool.namespace is None
            assert tool.method_name in ("add", "subtract")

    def test_instance_class_with_namespace(self):
        registry = ToolRegistry(name="test")
        greeter = Greeter()
        registry.register_from_class(greeter, namespace=True)
        tools = registry.list_tools()
        assert len(tools) == 2

        for tool_name in tools:
            tool = registry.get_tool(tool_name)
            assert tool is not None
            assert tool.namespace == "greeter"
            assert tool.method_name in ("hello", "goodbye")

    def test_instance_class_with_namespace_from_type(self):
        """When passing a class (not instance) with instance methods."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(Greeter, namespace="greet")
        tools = registry.list_tools()

        for tool_name in tools:
            tool = registry.get_tool(tool_name)
            assert tool is not None
            assert tool.namespace == "greet"


# ===========================================================================
# 7. Backward compatibility – existing behavior unchanged
# ===========================================================================


class TestBackwardCompatibility:
    """Ensure existing behavior is not broken by the new fields."""

    def test_tool_serialization_excludes_callable(self):
        tool = Tool.from_function(dummy_add, namespace="calc")
        data = tool.model_dump()
        assert "callable" not in data
        assert "namespace" in data
        assert "method_name" in data

    def test_register_plain_function(self):
        registry = ToolRegistry(name="test")
        registry.register(dummy_add)
        assert "dummy_add" in registry
        tool = registry.get_tool("dummy_add")
        assert tool is not None
        assert tool.run({"a": 1, "b": 2}) == 3

    def test_register_with_namespace(self):
        registry = ToolRegistry(name="test")
        registry.register(dummy_add, namespace="math")
        assert "math-dummy_add" in registry
        tool = registry.get_tool("math-dummy_add")
        assert tool is not None
        assert tool.run({"a": 5, "b": 3}) == 8

    def test_name_field_behavior_unchanged(self):
        """The name field should still work as before."""
        tool = Tool.from_function(dummy_add, name="custom_name")
        assert tool.name == "custom_name"
        assert tool.method_name == "custom_name"
