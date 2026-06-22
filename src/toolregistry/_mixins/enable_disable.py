"""Enable/disable mixin for ToolRegistry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ..events import ChangeEvent, ChangeEventType

if TYPE_CHECKING:
    from ..tool import Tool, ToolTag


class EnableDisableMixin:
    """Mixin providing tool enable/disable management."""

    # Type stubs for attributes/methods from other mixins
    _tools: dict[str, Tool]

    if TYPE_CHECKING:

        def _emit_change(self, event: ChangeEvent) -> None: ...

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._disabled: dict[str, str] = {}

    def disable(self, name: str, reason: str = "") -> None:
        """Disable a tool or namespace. Uses raw name (not normalized).

        Args:
            name: The tool name or namespace to disable.
            reason: Optional reason for disabling.
        """
        self._disabled[name] = reason
        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.DISABLE,
                tool_name=name,
                reason=reason or None,
            )
        )

    def enable(self, name: str) -> None:
        """Re-enable a tool or namespace.

        Args:
            name: The tool name or namespace to re-enable.
        """
        self._disabled.pop(name, None)
        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.ENABLE,
                tool_name=name,
            )
        )

    def is_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled (not disabled at method or group level).

        Args:
            tool_name: The tool name to check.

        Returns:
            True if the tool is enabled, False otherwise.
        """
        if tool_name in self._disabled:
            return False
        tool = self._tools.get(tool_name)
        if tool and tool.namespace and tool.namespace in self._disabled:
            return False
        return True

    def get_disable_reason(self, tool_name: str) -> str | None:
        """Get the reason a tool is disabled, or None if enabled.

        Method-level disable takes priority over group-level.

        Args:
            tool_name: The tool name to check.

        Returns:
            The disable reason string, or None if the tool is enabled.
        """
        if tool_name in self._disabled:
            return self._disabled[tool_name]
        tool = self._tools.get(tool_name)
        if tool and tool.namespace:
            return self._disabled.get(tool.namespace)
        return None

    def disable_by_tags(
        self,
        tags: set[ToolTag],
        *,
        match: Literal["any", "all"] = "any",
        reason: str = "Disabled by tag filter",
    ) -> list[str]:
        """Disable all tools whose metadata tags overlap with *tags*.

        Args:
            tags: Set of ToolTag values to match against.
            match: ``"any"`` disables tools that have at least one matching tag
                (default). ``"all"`` requires all tags to be present.
            reason: Disable reason recorded on each tool.

        Returns:
            List of tool names that were disabled.
        """
        if not tags:
            return []

        # Normalise the incoming tags to their string values so comparisons
        # work regardless of whether callers pass ToolTag enum members or
        # plain strings (ToolTag inherits from str, so this is transparent).
        tag_strs: set[str] = {t if isinstance(t, str) else t.value for t in tags}

        disabled: list[str] = []
        for name, tool in self._tools.items():
            if tool.metadata is None:
                continue
            # Skip tools that are already disabled.
            if not self.is_enabled(name):
                continue
            tool_tags = tool.metadata.all_tags
            if match == "any":
                matched = bool(tool_tags & tag_strs)
            else:
                matched = tag_strs.issubset(tool_tags)
            if matched:
                self.disable(name, reason=reason)
                disabled.append(name)
        return disabled

    # Fields safe to update at runtime via update_tool_metadata()
    _MUTABLE_METADATA_FIELDS: frozenset[str] = frozenset(
        {"think_augment", "defer", "search_hint", "tags"}
    )

    def update_tool_metadata(self, tool_name: str, **kwargs: object) -> None:
        """Update mutable metadata fields for a tool at runtime.

        Only whitelisted fields (think_augment, defer, search_hint) can be modified.

        Args:
            tool_name: The name of the tool to update.
            **kwargs: Field-value pairs to update.

        Raises:
            KeyError: If the tool is not found.
            ValueError: If an unknown or disallowed field is specified.
        """
        tool = self._tools.get(tool_name)
        if tool is None:
            raise KeyError(f"Tool not found: {tool_name}")
        for key in kwargs:
            if key not in self._MUTABLE_METADATA_FIELDS:
                raise ValueError(
                    f"Field '{key}' is not allowed. "
                    f"Allowed fields: {sorted(self._MUTABLE_METADATA_FIELDS)}"
                )
        for key, value in kwargs.items():
            setattr(tool.metadata, key, value)
        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.METADATA_UPDATE,
                tool_name=tool_name,
                metadata=dict(kwargs),
            )
        )

    def update_namespace_metadata(self, namespace: str, **kwargs: object) -> None:
        """Update mutable metadata fields for all tools in a namespace.

        Only whitelisted fields (think_augment, defer) can be modified.

        Args:
            namespace: The namespace to update.
            **kwargs: Field-value pairs to apply to all tools in the namespace.

        Raises:
            KeyError: If no tools are found in the namespace.
            ValueError: If an unknown or disallowed field is specified.
        """
        tools = [t for t in self._tools.values() if t.namespace == namespace]
        if not tools:
            raise KeyError(f"Namespace not found: {namespace}")
        for key in kwargs:
            if key not in self._MUTABLE_METADATA_FIELDS:
                raise ValueError(
                    f"Field '{key}' is not allowed. "
                    f"Allowed fields: {sorted(self._MUTABLE_METADATA_FIELDS)}"
                )
        for tool in tools:
            for key, value in kwargs.items():
                setattr(tool.metadata, key, value)
            self._emit_change(
                ChangeEvent(
                    event_type=ChangeEventType.METADATA_UPDATE,
                    tool_name=tool.name,
                    metadata=dict(kwargs),
                )
            )
