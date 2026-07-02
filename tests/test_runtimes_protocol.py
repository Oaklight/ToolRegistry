"""Tests for the PTC bridge layer (runtimes subpackage)."""

import pytest

from toolregistry.runtimes import (
    DirectProjection,
    ToolProjection,
    namespace_to_callables,
    validate_namespace,
)


# ---------------------------------------------------------------------------
# ToolProjection protocol
# ---------------------------------------------------------------------------


class TestToolProjection:
    def test_runtime_checkable(self):
        assert isinstance(DirectProjection(name="t", fn=lambda: None), ToolProjection)

    def test_custom_class_satisfies_protocol(self):
        class MyProjection:
            @property
            def name(self) -> str:
                return "custom"

            @property
            def doc(self) -> str | None:
                return "doc"

            def __call__(self, **kwargs):
                return kwargs

        assert isinstance(MyProjection(), ToolProjection)


# ---------------------------------------------------------------------------
# DirectProjection
# ---------------------------------------------------------------------------


class TestDirectProjection:
    def test_sync_callable(self):
        def add(a: int, b: int) -> int:
            return a + b

        proj = DirectProjection(name="add", fn=add, doc="Add two numbers.")
        assert proj.name == "add"
        assert proj.doc == "Add two numbers."
        assert proj(a=3, b=4) == 7

    def test_async_callable(self):
        async def multiply(a: int, b: int) -> int:
            return a * b

        proj = DirectProjection(name="multiply", fn=multiply)
        assert proj.name == "multiply"
        assert proj.doc is None
        assert proj(a=3, b=5) == 15

    def test_fn_attribute(self):
        def f():
            pass

        proj = DirectProjection(name="f", fn=f)
        assert proj.fn is f

    def test_no_doc(self):
        proj = DirectProjection(name="t", fn=lambda: 42)
        assert proj.doc is None
        assert proj() == 42


# ---------------------------------------------------------------------------
# validate_namespace
# ---------------------------------------------------------------------------


class TestValidateNamespace:
    def test_consistent_namespace(self):
        ns = {
            "add": DirectProjection(name="add", fn=lambda a, b: a + b),
            "mul": DirectProjection(name="mul", fn=lambda a, b: a * b),
        }
        validate_namespace(ns)  # should not raise

    def test_empty_namespace(self):
        validate_namespace({})  # should not raise

    def test_mismatched_key_raises(self):
        ns = {
            "wrong_name": DirectProjection(name="add", fn=lambda a, b: a + b),
        }
        with pytest.raises(ValueError, match="wrong_name.*add"):
            validate_namespace(ns)


# ---------------------------------------------------------------------------
# namespace_to_callables
# ---------------------------------------------------------------------------


class TestNamespaceToCallables:
    def test_converts_projections(self):
        add_proj = DirectProjection(name="add", fn=lambda a, b: a + b)
        mul_proj = DirectProjection(name="mul", fn=lambda a, b: a * b)
        ns = {"add": add_proj, "mul": mul_proj}

        callables = namespace_to_callables(ns)
        assert set(callables.keys()) == {"add", "mul"}
        assert callables["add"](a=2, b=3) == 5
        assert callables["mul"](a=2, b=3) == 6

    def test_empty(self):
        assert namespace_to_callables({}) == {}
