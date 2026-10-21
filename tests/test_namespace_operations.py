"""Field-driven namespace operations (#310).

``Tool.namespace`` and ``Tool.method_name`` are authoritative: every operation
rebuilds ``name`` from them instead of slicing registry keys.  These tests cover
both supported separators, the merge → spinoff → merge sequence, and separator
changes at runtime.
"""

from __future__ import annotations

import pytest

from toolregistry import ToolRegistry
from toolregistry._names import (
    is_in_namespace,
    namespace_prefix,
    strip_namespace,
)
from toolregistry.tool import Tool, ToolMetadata


def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def multiply(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b


def upper(text: str) -> str:
    """Upper-case a string."""
    return text.upper()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestNamespaceHelpers:
    @pytest.mark.parametrize(
        ("name", "sep", "expected"),
        [
            ("math.add", ".", "math"),
            ("math-add", "-", "math"),
            ("math_add", "-", None),
            ("plain", ".", None),
        ],
    )
    def test_namespace_prefix(self, name, sep, expected):
        assert namespace_prefix(name, sep) == expected

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_boundary_is_required(self, sep):
        assert is_in_namespace(f"math{sep}add", "math", sep)
        assert not is_in_namespace(f"math_ops{sep}add", "math", sep)
        assert not is_in_namespace("math", "math", sep)

    def test_empty_namespace_never_matches(self):
        assert not is_in_namespace("math-add", "", "-")

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_strip_returns_unchanged_for_other_namespaces(self, sep):
        assert strip_namespace(f"math{sep}add", "math", sep) == "add"
        assert strip_namespace(f"math_ops{sep}add", "math", sep) == f"math_ops{sep}add"


# ---------------------------------------------------------------------------
# Tool.requalify / qualified_name
# ---------------------------------------------------------------------------


class TestRequalify:
    @pytest.mark.parametrize("sep", ["-", "."])
    def test_flatten_and_requalify(self, sep):
        tool = Tool.from_function(add, namespace="math", sep=sep)

        assert tool.qualified_name == tool.name == f"math{sep}add"
        flat = tool.requalify(None, sep)
        assert (flat.name, flat.namespace, flat.method_name) == ("add", None, "add")
        moved = flat.requalify("stats", sep)
        assert moved.name == f"stats{sep}add"
        assert moved.namespace == "stats"

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_requalify_from_legacy_name_without_method_name(self, sep):
        tool = Tool(
            name=f"math{sep}add",
            description="legacy",
            parameters={},
            callable=add,
        )

        flat = tool.requalify(None, sep)
        assert flat.name == "add"
        assert flat.namespace is None
        assert flat.method_name == "add"


# ---------------------------------------------------------------------------
# spinoff
# ---------------------------------------------------------------------------


class TestSpinoffNamespaces:
    @pytest.mark.parametrize("sep", ["-", "."])
    def test_selects_by_namespace_field(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="math")
        registry.register(upper, namespace="text")

        spun = registry.spinoff("math")

        assert list(spun._tools) == ["add"]
        assert spun.name_sep == sep
        assert spun.get_tool("add").namespace is None
        assert list(registry._tools) == ["upper"]

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_boundary_does_not_match_a_longer_namespace(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="math_ops")
        registry.register(upper, namespace="math")

        spun = registry.spinoff("math")

        assert list(spun._tools) == ["upper"]
        assert list(registry._tools) == ["add"]

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_retain_namespace_keeps_qualified_names(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="math")
        registry.register(upper, namespace="text")

        spun = registry.spinoff("math", retain_namespace=True)

        key = f"math{sep}add"
        assert list(spun._tools) == [key]
        assert spun.get_tool(key).namespace == "math"
        # Tools move; retain only skips flattening in both registries.
        assert key not in registry._tools
        assert f"text{sep}upper" in registry._tools

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_prefix_is_normalized(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="MyMath")

        spun = registry.spinoff("MyMath")

        assert spun.name == "my_math"
        assert list(spun._tools) == ["add"]

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_invariant_keys_equal_tool_names(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="math")
        registry.register(multiply, namespace="math")

        spun = registry.spinoff("math", retain_namespace=True)

        assert all(key == tool.name for key, tool in spun._tools.items())
        assert all(key == tool.name for key, tool in registry._tools.items())

    def test_unknown_namespace_raises(self):
        registry = ToolRegistry()
        registry.register(add, namespace="math")

        with pytest.raises(ValueError, match="No tools with prefix 'text'"):
            registry.spinoff("text")

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_unqualified_tools_survive(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="math")
        registry.register(upper)

        registry.spinoff("math")

        assert list(registry._tools) == ["upper"]
        assert registry.get_tool("upper").namespace is None


# ---------------------------------------------------------------------------
# reduce_namespace
# ---------------------------------------------------------------------------


class TestReduceNamespace:
    @pytest.mark.parametrize("sep", ["-", "."])
    def test_leaves_unqualified_tools_alone(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="math")
        registry.register(upper)

        registry.reduce_namespace()

        assert set(registry._tools) == {"add", "upper"}
        assert registry.get_tool("add").namespace is None
        assert registry.get_tool("upper").namespace is None
        assert all(key == tool.name for key, tool in registry._tools.items())

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_noop_with_multiple_namespaces(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="math")
        registry.register(upper, namespace="text")

        registry.reduce_namespace()

        assert set(registry._tools) == {f"math{sep}add", f"text{sep}upper"}

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_collision_raises_without_mutation(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="math")
        registry.register(multiply, name="add")

        before = dict(registry._tools)
        with pytest.raises(ValueError, match="collide"):
            registry.reduce_namespace()

        assert registry._tools == before

    def test_reduces_prebuilt_namespaced_tool(self):
        """A ``Tool`` registered with its namespace already set is reduced.

        Registration does not populate ``_sub_registries`` for this path, so
        the operation must derive the set from the tool fields.
        """
        registry = ToolRegistry()
        registry.register(Tool.from_function(add, namespace="calc"))
        assert registry._sub_registries == set()

        registry.reduce_namespace()

        assert list(registry._tools) == ["add"]
        assert registry.get_tool("add").namespace is None


# ---------------------------------------------------------------------------
# merge and merge -> spinoff -> merge
# ---------------------------------------------------------------------------


class TestMergeSeparators:
    @pytest.mark.parametrize("sep", ["-", "."])
    def test_matching_separators(self, sep):
        left = ToolRegistry(name="left", name_sep=sep)
        right = ToolRegistry(name="right", name_sep=sep)
        left.register(add)
        right.register(multiply)

        left.merge(right)

        assert set(left._tools) == {f"left{sep}add", f"right{sep}multiply"}
        assert all(key == tool.name for key, tool in left._tools.items())

    def test_cross_separator_is_converted(self):
        left = ToolRegistry(name="left")  # "-"
        right = ToolRegistry(name="right", name_sep=".")  # "."
        left.register(add)
        right.register(multiply)

        left.merge(right)

        assert set(left._tools) == {"left-add", "right-multiply"}
        assert left.get_tool("right-multiply").namespace == "right"
        assert all(key == tool.name for key, tool in left._tools.items())

    def test_incoming_overrides_are_carried_and_rekeyed(self):
        left = ToolRegistry(name="left")
        right = ToolRegistry(name="right", name_sep=".")
        right.register(multiply)
        right.override("multiply", lambda a, b: a * b + 1)

        left.merge(right)

        assert list(left.list_overrides()) == ["right-multiply"]
        assert left.invoke("right-multiply", {"a": 2, "b": 3}).result == "7"
        restored = left.restore_override("right-multiply")
        assert restored.name == "right-multiply"

    def test_force_namespace_rebuilds_every_name(self):
        left = ToolRegistry(name="left")
        right = ToolRegistry(name="right", name_sep=".")
        left.register(add)
        right.register(multiply)

        left.merge(right, force_namespace=True)

        assert set(left._tools) == {"left-add", "left-multiply"}
        assert {tool.namespace for tool in left._tools.values()} == {"left"}

    def test_merge_spinoff_merge_sequence(self):
        a = ToolRegistry(name="a", name_sep=".")
        b = ToolRegistry(name="b")  # "-"
        a.register(add)
        b.register(multiply)

        a.merge(b)
        assert set(a._tools) == {"a.add", "b.multiply"}

        spun = a.spinoff("b")
        assert spun.name_sep == "."
        assert list(spun._tools) == ["multiply"]
        assert list(a._tools) == ["add"]

        a.merge(spun)
        assert set(a._tools) == {"a.add", "b.multiply"}
        assert a.get_tool("b.multiply").namespace == "b"
        assert all(key == tool.name for key, tool in a._tools.items())


# ---------------------------------------------------------------------------
# Runtime separator changes
# ---------------------------------------------------------------------------


class TestNameSepSetter:
    @pytest.mark.parametrize(("old", "new"), [("-", "."), (".", "-")])
    def test_rekeys_registered_tools_and_overrides(self, old, new):
        registry = ToolRegistry(name_sep=old)
        registry.register(add, namespace="math")
        registry.override(f"math{old}add", multiply)
        registry.register(upper)

        registry.name_sep = new

        assert set(registry._tools) == {f"math{new}add", "upper"}
        assert registry.get_tool(f"math{new}add").namespace == "math"
        assert list(registry.list_overrides()) == [f"math{new}add"]
        assert registry.restore_override(f"math{new}add").name == f"math{new}add"
        assert all(key == tool.name for key, tool in registry._tools.items())

    def test_collision_raises_without_mutation(self):
        registry = ToolRegistry()
        registry.register(add, namespace="math")
        # Fabricate the collision the public API cannot create: a dot-keyed tool
        # that requalifies to the same name as the registered hyphen key.
        legacy = Tool(
            name="math.add",
            description="legacy",
            parameters={},
            callable=multiply,
            namespace="math",
            method_name="add",
        )
        registry._tools["math.add"] = legacy

        before = dict(registry._tools)
        with pytest.raises(ValueError, match="collide"):
            registry.name_sep = "."

        assert registry._tools == before
        assert registry.name_sep == "-"

    def test_same_value_is_a_noop(self):
        registry = ToolRegistry()
        registry.register(add, namespace="math")

        registry.name_sep = "-"

        assert set(registry._tools) == {"math-add"}


# ---------------------------------------------------------------------------
# Disabled state follows the tool
# ---------------------------------------------------------------------------


class TestDisabledStateFollowsTools:
    @pytest.mark.parametrize(("old", "new"), [("-", "."), (".", "-")])
    def test_name_sep_change_keeps_disabled(self, old, new):
        registry = ToolRegistry(name_sep=old)
        registry.register(add, namespace="math")
        registry.register(multiply, namespace="math")
        registry.disable(f"math{old}multiply", reason="maintenance")

        registry.name_sep = new

        assert not registry.is_enabled(f"math{new}multiply")
        assert registry.is_enabled(f"math{new}add")
        assert f"math{new}multiply" in registry._disabled

    def test_name_sep_change_keeps_namespace_level_disable(self):
        registry = ToolRegistry()
        registry.register(add, namespace="math")
        registry.disable("math", reason="maintenance")

        registry.name_sep = "."

        assert not registry.is_enabled("math.add")

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_reduce_keeps_method_level_disable(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="calc")
        registry.disable(f"calc{sep}add", reason="maintenance")

        registry.reduce_namespace()

        assert list(registry._tools) == ["add"]
        assert not registry.is_enabled("add")
        assert registry.get_disable_reason("add") == "maintenance"

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_reduce_keeps_namespace_level_disable(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="calc")
        registry.register(multiply, namespace="calc")
        registry.disable("calc", reason="maintenance")

        registry.reduce_namespace()

        assert not registry.is_enabled("add")
        assert not registry.is_enabled("multiply")
        assert registry._disabled == {
            "add": "maintenance",
            "multiply": "maintenance",
        }

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_spinoff_moves_method_level_disable(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="math")
        registry.disable(f"math{sep}add", reason="maintenance")

        spun = registry.spinoff("math")

        assert not spun.is_enabled("add")
        assert spun.get_disable_reason("add") == "maintenance"
        assert f"math{sep}add" not in registry._disabled

    @pytest.mark.parametrize("sep", ["-", "."])
    def test_spinoff_retain_moves_disable_with_qualified_name(self, sep):
        registry = ToolRegistry(name_sep=sep)
        registry.register(add, namespace="math")
        registry.disable(f"math{sep}add", reason="maintenance")

        spun = registry.spinoff("math", retain_namespace=True)

        assert not spun.is_enabled(f"math{sep}add")
        assert spun.get_disable_reason(f"math{sep}add") == "maintenance"

    def test_merge_carries_disabled(self):
        left = ToolRegistry(name="left")
        right = ToolRegistry(name="right")
        right.register(multiply)
        right.disable("multiply", reason="maintenance")

        left.merge(right)

        assert not left.is_enabled("right-multiply")
        assert left.get_disable_reason("right-multiply") == "maintenance"

    def test_force_namespace_drops_stale_disabled_key(self):
        left = ToolRegistry(name="reg")
        right = ToolRegistry(name="other")
        left.register(add, namespace="m")
        right.register(multiply)
        left.disable("m-add", reason="maintenance")

        left.merge(right, force_namespace=True)

        assert "reg-add" in left._tools
        assert left.get_disable_reason("reg-add") == "maintenance"
        assert "m-add" not in left._disabled

    def test_merge_keep_existing_does_not_import_disabled(self):
        left = ToolRegistry(name="reg")
        right = ToolRegistry(name="reg")
        left.register(multiply, name="dup")
        right.register(multiply, name="dup")
        right.disable("dup", reason="maintenance")

        left.merge(right, keep_existing=True)

        assert "reg-dup" in left._tools
        assert left.is_enabled("reg-dup")

    def test_spinoff_inherits_execution_mode(self):
        registry = ToolRegistry()
        registry._execution_mode = "thread"
        registry.register(add, namespace="math")

        spun = registry.spinoff("math")

        assert spun._execution_mode == "thread"


# ---------------------------------------------------------------------------
# Discovery index invalidation
# ---------------------------------------------------------------------------


class TestNameSepChangeInvalidatesDiscovery:
    def test_discover_returns_rekeyed_name(self):
        registry = ToolRegistry(tool_discovery=True)
        registry.register(add, namespace="math")

        registry.name_sep = "."

        found = registry._tool_discovery.discover("math.add")
        assert [item["name"] for item in found] == ["math.add"]

    def test_discover_after_flip_drops_old_key(self):
        """A populated index must not survive the rename with stale ids."""
        registry = ToolRegistry(tool_discovery=True)
        registry.register(add, namespace="math")
        # Populate the index under the old separator first; a cold index
        # rebuilds from the current state and would hide the bug.
        assert [
            item["name"] for item in registry._tool_discovery.discover("math-add")
        ] == ["math-add"]

        registry.name_sep = "."

        found = [item["name"] for item in registry._tool_discovery.discover("math-add")]
        assert "math-add" not in found
        assert [
            item["name"] for item in registry._tool_discovery.discover("math.add")
        ] == ["math.add"]

    def test_call_deferred_uses_rekeyed_name(self):
        registry = ToolRegistry(tool_discovery=True)
        registry.register(
            Tool.from_function(add, metadata=ToolMetadata(defer=True)),
            namespace="math",
        )

        registry.name_sep = "."

        result = registry._tool_discovery.call_deferred("math.add", a=1, b=2)
        assert result == 3


class TestNamespaceOpsInvalidateDiscovery:
    """Renaming operations must not leave phantom document ids in the index."""

    @staticmethod
    def _names(registry, query):
        return [item["name"] for item in registry._tool_discovery.discover(query)]

    def test_reduce_namespace_drops_old_names(self):
        registry = ToolRegistry(tool_discovery=True)
        registry.register(add, namespace="calc")
        registry.register(multiply, namespace="calc")
        # Build the index under the qualified names.
        assert self._names(registry, "calc-add") == ["calc-add"]

        registry.reduce_namespace()

        assert self._names(registry, "add") == ["add"]
        assert "calc-add" not in self._names(registry, "calc-add")

    @pytest.mark.parametrize("retain", [True, False])
    def test_spinoff_drops_moved_names_from_source(self, retain):
        registry = ToolRegistry(tool_discovery=True)
        registry.register(add, namespace="math")
        registry.register(upper, namespace="text")
        assert self._names(registry, "math-add") == ["math-add"]

        registry.spinoff("math", retain_namespace=retain)

        assert "math-add" not in self._names(registry, "math-add")
        expected = "text-upper" if retain else "upper"
        assert self._names(registry, expected) == [expected]

    def test_merge_drops_old_names_on_both_sides(self):
        left = ToolRegistry(name="left", tool_discovery=True)
        right = ToolRegistry(name="right", tool_discovery=True)
        left.register(add)
        right.register(multiply)
        assert self._names(left, "add") == ["add"]
        assert self._names(right, "multiply") == ["multiply"]

        left.merge(right)

        assert self._names(left, "left-add") == ["left-add"]
        assert "add" not in self._names(left, "add")
        assert self._names(right, "right-multiply") == ["right-multiply"]
        assert "multiply" not in self._names(right, "multiply")
