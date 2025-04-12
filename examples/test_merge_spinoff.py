import unittest
from src.toolregistry.tool_registry import ToolRegistry


def create_sample_tool(registry, name):
    """Helper function to create a simple tool in a registry."""

    # Create a dynamic function with the given name
    def tool_func():
        return f"Result from {name}"

    # Set the function name to match the tool name
    tool_func.__name__ = name
    registry.register(tool_func)


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

    def test_basic_merge(self):
        """Test basic merge functionality."""
        self.registry_a.merge(self.registry_b)

        # Verify tools were merged
        self.assertEqual(len(self.registry_a.get_available_tools()), 4)
        self.assertIn("A.tool1", self.registry_a.get_available_tools())
        self.assertIn("B.tool3", self.registry_a.get_available_tools())

    def test_keep_existing_merge(self):
        """Test merge with keep_existing=True."""
        # Add conflicting tool names
        create_sample_tool(self.registry_a, "conflict")
        create_sample_tool(self.registry_b, "conflict")

        original_tool = self.registry_a.get_tool("conflict")
        self.registry_a.merge(self.registry_b, keep_existing=True)

        # Verify original tool was kept
        self.assertIs(self.registry_a.get_tool("A.conflict"), original_tool)
        self.assertNotIn("B.conflict", self.registry_a.get_available_tools())

    def test_overwrite_merge(self):
        """Test merge with keep_existing=False."""
        # Add conflicting tool names
        create_sample_tool(self.registry_a, "conflict")
        create_sample_tool(self.registry_b, "conflict")

        original_tool = self.registry_a.get_tool("conflict")
        self.registry_a.merge(self.registry_b, keep_existing=False)

        # Verify new tool overwrote original
        self.assertIsNot(self.registry_a.get_tool("B.conflict"), original_tool)
        self.assertNotIn("A.conflict", self.registry_a.get_available_tools())

    def test_multi_level_merge(self):
        """Test multi-level merge scenario."""
        # B merges C
        self.registry_b.merge(self.registry_c)
        # A merges B (which already contains C)
        self.registry_a.merge(self.registry_b)

        # Verify all tools are present with correct prefixes
        self.assertEqual(len(self.registry_a.get_available_tools()), 6)
        self.assertIn("B.C.tool5", self.registry_a.get_available_tools())
        self.assertIn("A.tool1", self.registry_a.get_available_tools())

    def test_basic_spinoff(self):
        """Test basic spinoff functionality."""

        # Create a tool with prefix
        # For prefixed tools, we need to create nested functions
        def sub_tool1():
            return "Result from sub.tool1"

        sub_tool1.__name__ = "sub.tool1"
        self.registry_a.register(sub_tool1)

        # Spinoff the 'sub' prefix
        sub_registry = self.registry_a.spinoff("sub")

        # Verify tools were moved correctly
        self.assertEqual(
            len(self.registry_a.get_available_tools()), 2
        )  # original tools remain
        self.assertEqual(len(sub_registry.get_available_tools()), 1)
        self.assertIn("tool1", sub_registry.get_available_tools())

    def test_multi_level_spinoff(self):
        """Test multi-level spinoff scenario."""

        # Create nested tools
        # For multi-level prefixed tools
        def sub1_sub2_tool1():
            return "Result from sub1.sub2.tool1"

        sub1_sub2_tool1.__name__ = "sub1.sub2.tool1"
        self.registry_a.register(sub1_sub2_tool1)

        # First spinoff sub1
        sub1_registry = self.registry_a.spinoff("sub1")
        # Then spinoff sub2 from sub1
        sub2_registry = sub1_registry.spinoff("sub2")

        # Verify tools were moved correctly through multiple levels
        self.assertEqual(len(sub2_registry.get_available_tools()), 1)
        self.assertIn("tool1", sub2_registry.get_available_tools())
        self.assertEqual(
            len(sub1_registry.get_available_tools()), 0
        )  # all tools were in sub2
        self.assertEqual(
            len(self.registry_a.get_available_tools()), 2
        )  # original tools remain

    def test_merge_after_spinoff(self):
        """Test merge after spinoff scenario."""

        # Create tools with prefix
        def sub_tool1():
            return "Result from sub.tool1"

        sub_tool1.__name__ = "sub.tool1"
        self.registry_a.register(sub_tool1)

        def sub_tool2():
            return "Result from sub.tool2"

        sub_tool2.__name__ = "sub.tool2"
        self.registry_b.register(sub_tool2)

        # Spinoff from A
        sub_a = self.registry_a.spinoff("sub")
        # Spinoff from B
        sub_b = self.registry_b.spinoff("sub")

        # Merge the two sub registries
        sub_a.merge(sub_b)

        # Verify merged tools
        self.assertEqual(len(sub_a.get_available_tools()), 2)
        self.assertIn("tool1", sub_a.get_available_tools())
        self.assertIn("tool2", sub_a.get_available_tools())

    def test_deep_nested_merge(self):
        """Test merging registries with multiple levels of nesting."""

        # Create nested tools in registry A
        def a_sub1_sub2_tool1():
            return "Result from a.sub1.sub2.tool1"

        a_sub1_sub2_tool1.__name__ = "a.sub1.sub2.tool1"
        self.registry_a.register(a_sub1_sub2_tool1)

        # Create nested tools in registry B
        def b_sub1_sub3_tool1():
            return "Result from b.sub1.sub3.tool1"

        b_sub1_sub3_tool1.__name__ = "b.sub1.sub3.tool1"
        self.registry_b.register(b_sub1_sub3_tool1)

        # Merge B into A
        self.registry_a.merge(self.registry_b)

        # Verify all tools are present with correct namespaces
        self.assertEqual(len(self.registry_a.get_available_tools()), 2)
        self.assertIn("A.a.sub1.sub2.tool1", self.registry_a.get_available_tools())
        self.assertIn("B.b.sub1.sub3.tool1", self.registry_a.get_available_tools())

    def test_multi_level_spinoff_chain(self):
        """Test chained spinoff operations on deeply nested tools."""

        # Create deeply nested tool
        def l1_l2_l3_tool1():
            return "Result from l1.l2.l3.tool1"

        l1_l2_l3_tool1.__name__ = "l1.l2.l3.tool1"
        self.registry_a.register(l1_l2_l3_tool1)

        # Spinoff level by level
        l1_reg = self.registry_a.spinoff("l1")
        l2_reg = l1_reg.spinoff("l2")
        l3_reg = l2_reg.spinoff("l3")

        # Verify tool is correctly moved to final registry
        self.assertEqual(len(l3_reg.get_available_tools()), 1)
        self.assertIn("tool1", l3_reg.get_available_tools())
        self.assertEqual(len(l2_reg.get_available_tools()), 0)
        self.assertEqual(len(l1_reg.get_available_tools()), 0)
        self.assertEqual(
            len(self.registry_a.get_available_tools()), 2
        )  # original tools


if __name__ == "__main__":
    unittest.main()
