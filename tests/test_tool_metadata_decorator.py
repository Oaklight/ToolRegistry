"""Tests for ``@tool_metadata`` (#442).

A declaration on the function is the only channel a class method has for
tags, deferral, hints or a title: class registration builds every tool through
``Tool.from_function`` and never accepts metadata itself.
"""

from __future__ import annotations

import pytest
from toolregistry import Tool, ToolMetadata, ToolRegistry, ToolTag, tool_metadata


class TestFromFunction:
    def test_declaration_reaches_the_tool(self) -> None:
        @tool_metadata(
            defer=True,
            tags={"read_only", "network"},
            title="Search",
            read_only_hint=True,
            idempotent_hint=True,
        )
        def search(query: str) -> list[str]:
            """Search things."""
            return [query]

        tool = Tool.from_function(search)

        assert tool.metadata.defer is True
        assert tool.metadata.tags == {ToolTag.READ_ONLY, ToolTag.NETWORK}
        assert tool.metadata.title == "Search"
        assert tool.metadata.read_only_hint is True
        assert tool.metadata.idempotent_hint is True

    def test_undeclared_function_keeps_the_defaults(self) -> None:
        def plain() -> str:
            """Do nothing."""
            return "ok"

        tool = Tool.from_function(plain)

        assert tool.metadata.defer is False
        assert tool.metadata.tags == set()
        assert tool.metadata.title is None

    def test_is_async_stays_auto_detected(self) -> None:
        @tool_metadata(defer=True)
        async def fetch() -> str:
            """Fetch."""
            return "ok"

        tool = Tool.from_function(fetch)

        assert tool.metadata.is_async is True
        assert tool.metadata.defer is True


class TestMergeWithExplicitMetadata:
    def test_explicit_values_win_and_defaults_are_filled(self) -> None:
        @tool_metadata(
            defer=True,
            title="Declared title",
            tags={"network"},
            search_hint="declared hint",
        )
        def search() -> str:
            """Search."""
            return "ok"

        tool = Tool.from_function(
            search,
            metadata=ToolMetadata(tags={ToolTag.READ_ONLY}, title="Explicit"),
        )

        # Explicit, non-default values win.
        assert tool.metadata.tags == {ToolTag.READ_ONLY}
        assert tool.metadata.title == "Explicit"
        # Fields left at their default are filled from the declaration.
        assert tool.metadata.defer is True
        assert tool.metadata.search_hint == "declared hint"

    def test_explicit_metadata_can_disable_a_declared_field(self) -> None:
        @tool_metadata(title="Declared", defer=True)
        def search() -> str:
            """Search."""
            return "ok"

        tool = Tool.from_function(search, metadata=ToolMetadata(title="Explicit"))

        assert tool.metadata.title == "Explicit"
        # ``defer`` was left at its default (False), so the declaration wins.
        assert tool.metadata.defer is True


class TestStacking:
    def test_outer_declaration_wins(self) -> None:
        # The topmost decorator is applied last, so it is the outer one.
        @tool_metadata(defer=False, title="Outer")
        @tool_metadata(defer=True, title="Inner")
        def search() -> str:
            """Search."""
            return "ok"

        tool = Tool.from_function(search)

        assert tool.metadata.defer is False
        assert tool.metadata.title == "Outer"

    def test_disjoint_declarations_merge(self) -> None:
        @tool_metadata(title="Outer")
        @tool_metadata(defer=True)
        def search() -> str:
            """Search."""
            return "ok"

        tool = Tool.from_function(search)

        assert tool.metadata.title == "Outer"
        assert tool.metadata.defer is True


class TestClassRegistration:
    """Class registration needs no new scan: bound methods delegate."""

    @staticmethod
    def _registry() -> ToolRegistry:
        class Tools:
            @staticmethod
            @tool_metadata(defer=True, tags={"read_only"}, title="Static")
            def static() -> str:
                """Static tool."""
                return "static"

            @tool_metadata(search_hint="instance hint", idempotent_hint=True)
            def instance(self) -> str:
                """Instance tool."""
                return "instance"

        registry = ToolRegistry()
        registry.register(Tools, source="class", namespace="cls")
        return registry

    def test_static_method_declaration_is_applied(self) -> None:
        tool = self._registry()._tools["cls-static"]

        assert tool.metadata.defer is True
        assert tool.metadata.tags == {ToolTag.READ_ONLY}
        assert tool.metadata.title == "Static"

    def test_instance_method_declaration_is_applied(self) -> None:
        tool = self._registry()._tools["cls-instance"]

        assert tool.metadata.search_hint == "instance hint"
        assert tool.metadata.idempotent_hint is True


class TestValidation:
    @pytest.mark.parametrize(
        "name",
        ["is_async", "source", "source_detail", "schema_hash", "last_refreshed_at"],
    )
    def test_pipeline_fields_are_refused(self, name: str) -> None:
        with pytest.raises(TypeError, match="Cannot declare"):
            tool_metadata(**{name: True})

    def test_unknown_field_is_refused(self) -> None:
        with pytest.raises(TypeError, match="Cannot declare"):
            tool_metadata(not_a_field=True)

    def test_non_function_target_is_refused(self) -> None:
        with pytest.raises(TypeError, match="function or method"):
            tool_metadata(defer=True)(object())  # type: ignore[arg-type]
