"""A function-local annotation is recorded as a degraded parameter (#466).

This module needs ``from __future__ import annotations``: without it the
annotation is evaluated when the function is defined, and a type local to
the enclosing function would already be an object.  With it, the annotation
stays a string and is resolved through the function's globals, where the
local name does not exist.
"""

from __future__ import annotations

import pytest

from toolregistry import Tool


def _factory():
    class LocalModel:
        """Visible only inside ``_factory``."""

    def tool(x: LocalModel) -> int:
        """Take a locally defined type."""
        return 1

    return tool


def test_the_degraded_parameter_is_named_on_the_metadata() -> None:
    func = _factory()

    with pytest.warns(UserWarning, match="cannot be represented"):
        tool = Tool.from_function(func, name="local_annotation")

    assert tool.metadata.unresolved_parameters == ("x",)
    # The published schema is still the degraded, unconstrained one.
    assert "type" not in tool.parameters["properties"]["x"]
    # ``to_dict`` serializes the metadata, so a server can report it.
    assert tool.to_dict()["metadata"]["unresolved_parameters"] == ("x",)


def test_a_resolved_annotation_leaves_the_field_empty() -> None:
    def tool(count: int) -> int:
        return count

    built = Tool.from_function(tool, name="resolved")

    assert built.metadata.unresolved_parameters == ()
