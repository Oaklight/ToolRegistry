"""Enable/disable mixin for ToolRegistry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..events import ChangeEvent, ChangeEventType

if TYPE_CHECKING:
    from ..tool import Tool


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
