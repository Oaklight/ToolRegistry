"""Function-local annotations: degradation and ``localns`` resolution (#466).

This module needs ``from __future__ import annotations``: without it the
annotation is evaluated when the function is defined, and a type local to
the enclosing function would already be an object.  With it, the annotation
stays a string and is resolved through the function's globals, where the
local name does not exist unless the caller supplies it as ``localns``.
"""

from __future__ import annotations

import pytest

from toolregistry import Tool, ToolRegistry


def _local_tool():
    """Build the issue's tool with every annotation name local to the factory."""
    from enum import Enum
    from typing import Annotated

    from pydantic import Field

    class LocalColor(str, Enum):
        """Visible only inside ``_local_tool``."""

        RED = "red"
        BLUE = "blue"

    def bounded(x: Annotated[int, Field(ge=0, le=100)], color: LocalColor) -> int:
        """Take a bounded integer and a local enum."""
        return x

    return bounded, locals()


def test_localns_resolves_a_function_local_annotation() -> None:
    func, namespace = _local_tool()

    tool = Tool.from_function(func, name="bounded", localns=namespace)

    assert tool.metadata.unresolved_parameters == ()
    x = tool.parameters["properties"]["x"]
    assert x["minimum"] == 0
    assert x["maximum"] == 100


def test_without_localns_the_degradation_is_still_reported() -> None:
    func, _namespace = _local_tool()

    with pytest.warns(UserWarning, match="cannot be represented"):
        tool = Tool.from_function(func, name="bounded")

    assert tool.metadata.unresolved_parameters == ("color", "x")
    assert "minimum" not in tool.parameters["properties"]["x"]


def test_register_forwards_localns() -> None:
    func, namespace = _local_tool()
    registry = ToolRegistry()

    registry.register(func, localns=namespace)

    tool = registry.get_tool("bounded")
    assert tool is not None
    assert tool.metadata.unresolved_parameters == ()
    assert tool.parameters["properties"]["x"]["minimum"] == 0


def test_register_without_localns_still_reports_the_degradation() -> None:
    func, _namespace = _local_tool()
    registry = ToolRegistry()

    with pytest.warns(UserWarning, match="cannot be represented"):
        registry.register(func)

    tool = registry.get_tool("bounded")
    assert tool is not None
    assert tool.metadata.unresolved_parameters == ("color", "x")


@pytest.mark.asyncio
async def test_register_async_forwards_localns() -> None:
    func, namespace = _local_tool()
    registry = ToolRegistry()

    await registry.register_async(func, localns=namespace)

    tool = registry.get_tool("bounded")
    assert tool is not None
    assert tool.metadata.unresolved_parameters == ()
    assert tool.parameters["properties"]["x"]["minimum"] == 0


def test_the_decorator_form_forwards_localns() -> None:
    registry = ToolRegistry()

    def build() -> None:
        from typing import Annotated

        from pydantic import Field

        @registry.register(localns=locals())
        def bounded(x: Annotated[int, Field(ge=0, le=100)]) -> int:
            """Bounded."""
            return x

    build()

    tool = registry.get_tool("bounded")
    assert tool is not None
    assert tool.metadata.unresolved_parameters == ()
    assert tool.parameters["properties"]["x"]["maximum"] == 100


def test_a_resolved_annotation_leaves_the_field_empty() -> None:
    def tool(count: int) -> int:
        return count

    built = Tool.from_function(tool, name="resolved")

    assert built.metadata.unresolved_parameters == ()


def _plain_local_class_tool():
    class LocalModel:
        """Visible only inside this factory."""

    def tool(x: LocalModel) -> int:
        return 1

    return tool


def test_a_plain_local_class_is_reported_and_serialized() -> None:
    """#469's degradation signal, kept: the class has no schema either way."""
    with pytest.warns(UserWarning, match="cannot be represented"):
        tool = Tool.from_function(_plain_local_class_tool(), name="local_class")

    assert tool.metadata.unresolved_parameters == ("x",)
    assert tool.to_dict()["metadata"]["unresolved_parameters"] == ("x",)
