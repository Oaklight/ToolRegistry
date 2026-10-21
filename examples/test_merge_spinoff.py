"""Examples of merge() / spinoff() / reduce_namespace().

Runnable with ``python examples/test_merge_spinoff.py``.  The default separator
is ``-``; one test sets ``name_sep="."`` to show cross-separator merging.
"""

import unittest

from toolregistry.tool_registry import ToolRegistry
from toolregistry.utils import normalize_tool_name


def create_sample_tool(registry, name, namespace=None):
    """Register a trivial tool in *registry*."""

    def tool_func():
        return f"result_from_{normalize_tool_name(name)}"

    tool_func.__name__ = name
    registry.register(tool_func, namespace=namespace)


class TestMergeAndSpinoff(unittest.TestCase):
    def setUp(self):
        """Create three registries with two unqualified tools each."""
        self.registry_a = ToolRegistry("a")
        self.registry_b = ToolRegistry("b")

        for name in ("tool1", "tool2"):
            create_sample_tool(self.registry_a, name)
        for name in ("tool3", "tool4"):
            create_sample_tool(self.registry_b, name)

    def test_merge_with_force_namespace(self):
        """Every tool is prefixed with the receiving registry's name."""
        self.registry_a.merge(self.registry_b, force_namespace=True)

        self.assertEqual(
            set(self.registry_a.list_tools()),
            {"a-tool1", "a-tool2", "a-tool3", "a-tool4"},
        )
        self.assertEqual(
            {tool.namespace for tool in self.registry_a._tools.values()}, {"a"}
        )

    def test_merge_without_force_namespace(self):
        """Each side keeps its own registry-name prefix."""
        self.registry_a.merge(self.registry_b, force_namespace=False)

        self.assertEqual(
            set(self.registry_a.list_tools()),
            {"a-tool1", "a-tool2", "b-tool3", "b-tool4"},
        )

    def test_merge_across_separators(self):
        """Incoming names are converted to the receiving separator."""
        self.registry_a.name_sep = "."
        self.registry_a.merge(self.registry_b, force_namespace=False)

        names = set(self.registry_a.list_tools())
        self.assertEqual(names, {"a.tool1", "a.tool2", "b.tool3", "b.tool4"})
        self.assertTrue(
            all(key == tool.name for key, tool in self.registry_a._tools.items())
        )

    def test_spinoff(self):
        """The prefix is removed from the extracted tools by default."""
        create_sample_tool(self.registry_a, "tool1", namespace="sub")
        create_sample_tool(self.registry_a, "tool2", namespace="sub")

        sub_registry = self.registry_a.spinoff("sub")

        self.assertEqual(set(sub_registry.list_tools()), {"tool1", "tool2"})
        self.assertEqual(sub_registry.name_sep, "-")
        # The source keeps its unqualified tools and loses the namespaced ones.
        self.assertEqual(set(self.registry_a.list_tools()), {"tool1", "tool2"})
        self.assertEqual(self.registry_a.get_tool("tool1").namespace, None)

    def test_spinoff_with_retain_namespace(self):
        """``retain_namespace=True`` keeps the qualified names."""
        create_sample_tool(self.registry_a, "tool1", namespace="retain")
        create_sample_tool(self.registry_a, "tool2", namespace="retain")

        sub_registry = self.registry_a.spinoff("retain", retain_namespace=True)

        self.assertEqual(
            set(sub_registry.list_tools()), {"retain-tool1", "retain-tool2"}
        )
        self.assertEqual(sub_registry.get_tool("retain-tool1").namespace, "retain")

    def test_spinoff_unknown_namespace(self):
        with self.assertRaises(ValueError):
            self.registry_a.spinoff("nonexistent")

    def test_merge_after_spinoff(self):
        """Both spun-off registries are named after the namespace."""
        create_sample_tool(self.registry_a, "tool1", namespace="sub")
        create_sample_tool(self.registry_b, "tool2", namespace="sub")

        sub_a = self.registry_a.spinoff("sub")
        sub_b = self.registry_b.spinoff("sub")
        sub_a.merge(sub_b, force_namespace=False)

        self.assertEqual(set(sub_a.list_tools()), {"sub-tool1", "sub-tool2"})

    def test_reduce_namespace_leaves_unqualified_tools_alone(self):
        """A single remaining namespace is flattened; unqualified tools stay."""
        registry = ToolRegistry("calc")
        create_sample_tool(registry, "add", namespace="math")
        create_sample_tool(registry, "helper")

        registry.reduce_namespace()

        self.assertEqual(set(registry.list_tools()), {"add", "helper"})


if __name__ == "__main__":
    unittest.main()
