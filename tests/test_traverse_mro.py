"""Tests for traverse_mro parameter in register_from_class (Issue #52)."""

from toolregistry.tool_registry import ToolRegistry


# ---------------------------------------------------------------------------
# Helper classes for testing MRO traversal
# ---------------------------------------------------------------------------


class BaseTools:
    """Base class with static methods."""

    @staticmethod
    def base_method() -> str:
        """A method defined only in the base class."""
        return "base"

    @staticmethod
    def shared_method() -> str:
        """A method that may be overridden by subclasses."""
        return "base_shared"


class ChildTools(BaseTools):
    """Child class that adds its own static method."""

    @staticmethod
    def child_method() -> str:
        """A method defined only in the child class."""
        return "child"


class OverrideTools(BaseTools):
    """Child class that overrides a parent method."""

    @staticmethod
    def shared_method() -> str:
        """Override the parent's shared_method."""
        return "override_shared"

    @staticmethod
    def override_only() -> str:
        """A method defined only in the override class."""
        return "override_only"


class GrandchildTools(OverrideTools):
    """Grandchild class to test deep MRO traversal."""

    @staticmethod
    def grandchild_method() -> str:
        """A method defined only in the grandchild class."""
        return "grandchild"


# Instance method hierarchy for testing instance method MRO traversal


class BaseInstance:
    """Base class with instance methods."""

    def base_instance_method(self) -> str:
        """An instance method defined only in the base class."""
        return "base_instance"

    def shared_instance_method(self) -> str:
        """An instance method that may be overridden."""
        return "base_shared_instance"


class ChildInstance(BaseInstance):
    """Child class with its own instance method."""

    def child_instance_method(self) -> str:
        """An instance method defined only in the child class."""
        return "child_instance"


class OverrideInstance(BaseInstance):
    """Child class that overrides a parent instance method."""

    def shared_instance_method(self) -> str:
        """Override the parent's shared_instance_method."""
        return "override_shared_instance"


# ===========================================================================
# 1. Default behavior (traverse_mro=False) – static methods
# ===========================================================================


class TestStaticMethodsDefaultBehavior:
    """Verify that traverse_mro=False only registers directly defined static methods."""

    def test_child_only_registers_own_methods(self):
        """ChildTools should only register child_method, not base_method or shared_method."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(ChildTools, traverse_mro=False)
        tools = registry.list_tools()
        assert "child_method" in tools
        assert "base_method" not in tools
        assert "shared_method" not in tools

    def test_base_registers_own_methods(self):
        """BaseTools should register base_method and shared_method."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(BaseTools, traverse_mro=False)
        tools = registry.list_tools()
        assert "base_method" in tools
        assert "shared_method" in tools

    def test_override_registers_own_methods(self):
        """OverrideTools should register shared_method and override_only, not base_method."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(OverrideTools, traverse_mro=False)
        tools = registry.list_tools()
        assert "shared_method" in tools
        assert "override_only" in tools
        assert "base_method" not in tools

    def test_default_parameter_is_false(self):
        """Calling without traverse_mro should behave the same as traverse_mro=False."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(ChildTools)
        tools = registry.list_tools()
        assert "child_method" in tools
        assert "base_method" not in tools


# ===========================================================================
# 2. traverse_mro=True – static methods
# ===========================================================================


class TestStaticMethodsMROTraversal:
    """Verify that traverse_mro=True includes inherited static methods."""

    def test_child_includes_inherited_methods(self):
        """ChildTools with traverse_mro=True should include base_method and shared_method."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(ChildTools, traverse_mro=True)
        tools = registry.list_tools()
        assert "child_method" in tools
        assert "base_method" in tools
        assert "shared_method" in tools

    def test_child_inherited_method_callable(self):
        """Inherited methods should be callable and return correct results."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(ChildTools, traverse_mro=True)
        base_tool = registry.get_tool("base_method")
        assert base_tool is not None
        assert base_tool.run({}) == "base"

    def test_override_uses_subclass_version(self):
        """When subclass overrides a method, only the subclass version is registered."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(OverrideTools, traverse_mro=True)
        tools = registry.list_tools()
        assert "shared_method" in tools
        assert "base_method" in tools
        assert "override_only" in tools

        # Verify the override version is used
        shared_tool = registry.get_tool("shared_method")
        assert shared_tool is not None
        assert shared_tool.run({}) == "override_shared"

    def test_grandchild_deep_mro(self):
        """GrandchildTools should include methods from all ancestors."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(GrandchildTools, traverse_mro=True)
        tools = registry.list_tools()
        assert "grandchild_method" in tools
        assert "shared_method" in tools
        assert "base_method" in tools
        assert "override_only" in tools

        # shared_method should be OverrideTools' version (closest in MRO)
        shared_tool = registry.get_tool("shared_method")
        assert shared_tool is not None
        assert shared_tool.run({}) == "override_shared"

    def test_object_methods_excluded(self):
        """Methods from object class should never be registered."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(BaseTools, traverse_mro=True)
        tools = registry.list_tools()
        # object methods like __init__, __str__, etc. should not appear
        for tool_name in tools:
            assert not tool_name.startswith("__")
        # Common object methods should not be present
        assert "__init__" not in tools
        assert "__str__" not in tools
        assert "__repr__" not in tools
        assert "__hash__" not in tools

    def test_base_class_same_with_or_without_mro(self):
        """For a class with no parents (besides object), traverse_mro should give same result."""
        registry_no_mro = ToolRegistry(name="test1")
        registry_no_mro.register_from_class(BaseTools, traverse_mro=False)

        registry_with_mro = ToolRegistry(name="test2")
        registry_with_mro.register_from_class(BaseTools, traverse_mro=True)

        assert sorted(registry_no_mro.list_tools()) == sorted(
            registry_with_mro.list_tools()
        )


# ===========================================================================
# 3. traverse_mro with namespace – static methods
# ===========================================================================


class TestStaticMethodsMROWithNamespace:
    """Verify that traverse_mro works correctly with namespace."""

    def test_mro_with_namespace(self):
        """Inherited methods should also get the namespace prefix."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(ChildTools, with_namespace=True, traverse_mro=True)
        tools = registry.list_tools()
        # All tools should have the namespace prefix
        for tool_name in tools:
            tool = registry.get_tool(tool_name)
            assert tool is not None
            assert tool.namespace == "child_tools"

        # Should have 3 methods: child_method, base_method, shared_method
        method_names = {
            registry.get_tool(t).method_name
            for t in tools  # type: ignore[union-attr]
        }
        assert method_names == {"child_method", "base_method", "shared_method"}

    def test_mro_with_custom_namespace(self):
        """Custom namespace should be applied to all inherited methods."""
        registry = ToolRegistry(name="test")
        registry.register_from_class(
            ChildTools, with_namespace="my_tools", traverse_mro=True
        )
        tools = registry.list_tools()
        for tool_name in tools:
            tool = registry.get_tool(tool_name)
            assert tool is not None
            assert tool.namespace == "my_tools"


# ===========================================================================
# 4. Instance method MRO traversal
# ===========================================================================


class TestInstanceMethodsMROTraversal:
    """Verify that traverse_mro works for instance methods."""

    def test_instance_default_no_mro(self):
        """Without traverse_mro, instance methods from parent should still be visible via dir()."""
        registry = ToolRegistry(name="test")
        child = ChildInstance()
        registry.register_from_class(child, traverse_mro=False)
        tools = registry.list_tools()
        # dir() includes inherited methods, so they should be present
        assert "child_instance_method" in tools
        assert "base_instance_method" in tools
        assert "shared_instance_method" in tools

    def test_instance_with_mro(self):
        """With traverse_mro=True, instance methods from parent should be included."""
        registry = ToolRegistry(name="test")
        child = ChildInstance()
        registry.register_from_class(child, traverse_mro=True)
        tools = registry.list_tools()
        assert "child_instance_method" in tools
        assert "base_instance_method" in tools
        assert "shared_instance_method" in tools

    def test_instance_override_uses_subclass_version(self):
        """When subclass overrides an instance method, the subclass version is used."""
        registry = ToolRegistry(name="test")
        override = OverrideInstance()
        registry.register_from_class(override, traverse_mro=True)
        tools = registry.list_tools()
        assert "shared_instance_method" in tools
        assert "base_instance_method" in tools

        shared_tool = registry.get_tool("shared_instance_method")
        assert shared_tool is not None
        assert shared_tool.run({}) == "override_shared_instance"

    def test_instance_object_methods_excluded(self):
        """Methods from object class should never be registered for instances."""
        registry = ToolRegistry(name="test")
        child = ChildInstance()
        registry.register_from_class(child, traverse_mro=True)
        tools = registry.list_tools()
        for tool_name in tools:
            assert not tool_name.startswith("__")

    def test_instance_with_namespace_and_mro(self):
        """Instance methods with namespace and MRO traversal."""
        registry = ToolRegistry(name="test")
        child = ChildInstance()
        registry.register_from_class(child, with_namespace=True, traverse_mro=True)
        tools = registry.list_tools()
        for tool_name in tools:
            tool = registry.get_tool(tool_name)
            assert tool is not None
            assert tool.namespace == "child_instance"


# ===========================================================================
# 5. Edge cases
# ===========================================================================


class TestTraverseMROEdgeCases:
    """Edge cases for traverse_mro."""

    def test_class_with_no_methods(self):
        """A class with no public methods should register nothing."""

        class EmptyClass:
            pass

        registry = ToolRegistry(name="test")
        registry.register_from_class(EmptyClass, traverse_mro=True)
        assert registry.list_tools() == []

    def test_class_with_only_private_methods(self):
        """A class with only private methods should register nothing."""

        class PrivateOnly:
            @staticmethod
            def _private_method() -> str:
                return "private"

        registry = ToolRegistry(name="test")
        registry.register_from_class(PrivateOnly, traverse_mro=True)
        assert registry.list_tools() == []

    def test_multiple_inheritance_mro(self):
        """Test MRO traversal with multiple inheritance."""

        class MixinA:
            @staticmethod
            def mixin_a_method() -> str:
                return "mixin_a"

        class MixinB:
            @staticmethod
            def mixin_b_method() -> str:
                return "mixin_b"

        class Combined(MixinA, MixinB):
            @staticmethod
            def combined_method() -> str:
                return "combined"

        registry = ToolRegistry(name="test")
        registry.register_from_class(Combined, traverse_mro=True)
        tools = registry.list_tools()
        assert "mixin_a_method" in tools
        assert "mixin_b_method" in tools
        assert "combined_method" in tools
