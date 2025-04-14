import unittest

from toolregistry.tool_registry import ToolRegistry
from toolregistry.utils import normalize_tool_name


def create_sample_tool(registry, name, namespace=None):
    """Helper function to create a simple tool in a registry."""

    def tool_func():
        return f"result_from_{normalize_tool_name(name)}"

    tool_func.__name__ = name
    registry.register(tool_func, namespace=namespace)


class TestMergeAndSpinoff(unittest.TestCase):
    def setUp(self):
        """Create sample registries for testing."""
        self.registry_a = ToolRegistry("A")
        self.registry_b = ToolRegistry("B")
        self.registry_c = ToolRegistry("C")

        # Populate with sample tools
        create_sample_tool(self.registry_a, "tool1")
        create_sample_tool(self.registry_a, "tool2")
        create_sample_tool(self.registry_b, "tool3")
        create_sample_tool(self.registry_b, "tool4")
        create_sample_tool(self.registry_c, "tool5")
        create_sample_tool(self.registry_c, "tool6")

    def test_merge_with_force_namespace(self):
        """Test merge functionality with force_namespace=True."""
        self.registry_a.merge(self.registry_b, force_namespace=True)
        available = self.registry_a.get_available_tools()
        self.assertEqual(len(available), 4)
        self.assertIn("a.tool1", available)
        self.assertIn("a.tool3", available)

    def test_merge_without_force_namespace(self):
        """Test merge functionality with force_namespace=False."""
        self.registry_a.merge(self.registry_b, force_namespace=False)
        available = self.registry_a.get_available_tools()
        self.assertEqual(len(available), 4)
        self.assertIn("a.tool1", available)
        self.assertIn("b.tool3", available)

    def test_spinoff(self):
        """Test spinoff functionality."""
        create_sample_tool(self.registry_a, "tool1", namespace="sub")
        create_sample_tool(self.registry_a, "tool2", namespace="sub")

        sub_registry = self.registry_a.spinoff("sub")
        self.assertEqual(len(sub_registry.get_available_tools()), 2)
        self.assertIn("tool1", sub_registry.get_available_tools())
        self.assertIn("tool2", sub_registry.get_available_tools())

        remaining_tools = self.registry_a.get_available_tools()
        self.assertEqual(len(remaining_tools), 2)
        self.assertIn("tool1", remaining_tools)
        self.assertIn("tool2", remaining_tools)

    def test_merge_after_spinoff(self):
        """Test merging spinoff registries."""
        create_sample_tool(self.registry_a, "tool1", namespace="sub")
        create_sample_tool(self.registry_b, "tool2", namespace="sub")

        sub_a = self.registry_a.spinoff("sub")
        sub_b = self.registry_b.spinoff("sub")

        sub_a.merge(sub_b, force_namespace=False)
        self.assertEqual(len(sub_a.get_available_tools()), 2)
        self.assertIn("sub.tool1", sub_a.get_available_tools())
        self.assertIn("sub.tool2", sub_a.get_available_tools())

    def test_merge_with_conflicting_and_empty_registry(self):
        """Test merge functionality with conflicting namespaces and empty registry."""
        # Conflicting namespaces
        create_sample_tool(self.registry_a, "tool1", namespace="conflict")
        create_sample_tool(self.registry_b, "tool1", namespace="conflict")

        self.registry_a.merge(self.registry_b, force_namespace=False)
        available = self.registry_a.get_available_tools()
        self.assertIn("conflict.tool1", available)
        self.assertEqual(len(available), 5)

        # Empty registry
        empty_registry = ToolRegistry("Empty")
        self.registry_a.merge(empty_registry, force_namespace=False)
        available = self.registry_a.get_available_tools()
        self.assertEqual(len(available), 5)
        self.assertIn("conflict.tool1", available)

    def test_spinoff_with_empty_namespace(self):
        """Test spinoff functionality with an empty namespace."""
        with self.assertRaises(ValueError):
            sub_registry = self.registry_a.spinoff("nonexistent")

    def test_spinoff_with_retain_namespace(self):
        """Test spinoff functionality with retain_namespace parameter."""
        create_sample_tool(self.registry_a, "tool1", namespace="retain")
        create_sample_tool(self.registry_a, "tool2", namespace="retain")

        # Case 1: retain_namespace=True
        sub_registry_retain = self.registry_a.spinoff("retain", retain_namespace=True)
        self.assertEqual(len(sub_registry_retain.get_available_tools()), 2)
        self.assertIn("retain.tool1", sub_registry_retain.get_available_tools())
        self.assertIn("retain.tool2", sub_registry_retain.get_available_tools())

        # Case 2: retain_namespace=False
        create_sample_tool(self.registry_a, "tool3", namespace="remove")
        create_sample_tool(self.registry_a, "tool4", namespace="remove")
        sub_registry_remove = self.registry_a.spinoff("remove", retain_namespace=False)
        self.assertEqual(len(sub_registry_remove.get_available_tools()), 2)
        self.assertIn("tool3", sub_registry_remove.get_available_tools())
        self.assertIn("tool4", sub_registry_remove.get_available_tools())

        """Test complex spinoff and merge scenarios."""
        create_sample_tool(self.registry_a, "tool1", namespace="complex")
        create_sample_tool(self.registry_a, "tool2", namespace="complex")
        create_sample_tool(self.registry_b, "tool3", namespace="complex")
        create_sample_tool(self.registry_b, "tool4", namespace="complex")

        sub_a = self.registry_a.spinoff("complex")
        sub_b = self.registry_b.spinoff("complex")

        sub_a.merge(sub_b, force_namespace=True)
        self.assertEqual(len(sub_a.get_available_tools()), 4)
        self.assertIn("complex.tool1", sub_a.get_available_tools())
        self.assertIn("complex.tool3", sub_a.get_available_tools())


if __name__ == "__main__":
    unittest.main()
