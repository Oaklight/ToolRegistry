"""Event types and data classes for ToolRegistry change notifications.

This module provides the event infrastructure for the callback mechanism,
enabling subscribers to receive notifications when tool state changes occur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeAlias
from collections.abc import Callable


if TYPE_CHECKING:
    from .tool import Tool
    from .tool_registry import ToolRegistry


class ChangeEventType(str, Enum):
    """Types of change events that can occur in ToolRegistry.

    Attributes:
        REGISTER: A tool was registered.
        UNREGISTER: A tool was unregistered.
        ENABLE: A tool was enabled.
        DISABLE: A tool was disabled.
        REFRESH: A single tool was refreshed.
        REFRESH_ALL: All tools were refreshed/reloaded.
        METADATA_UPDATE: A tool's metadata was updated at runtime.
    """

    REGISTER = "register"
    UNREGISTER = "unregister"
    ENABLE = "enable"
    DISABLE = "disable"
    REFRESH = "refresh"
    REFRESH_ALL = "refresh_all"
    PERMISSION_DENIED = "permission_denied"
    PERMISSION_ASKED = "permission_asked"
    METADATA_UPDATE = "metadata_update"
    TOOL_ERROR = "tool_error"


@dataclass(frozen=True)
class ChangeEvent:
    """Immutable event object passed to change callbacks.

    Attributes:
        event_type: The type of change that occurred.
        tool_name: Name of the affected tool, or None for bulk operations.
        reason: Optional reason string, primarily used for disable events.
        metadata: Optional additional context data.
    """

    event_type: ChangeEventType
    tool_name: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


ChangeCallback: TypeAlias = Callable[[ChangeEvent], None]
"""Callback signature: receives a ChangeEvent, returns nothing."""

PostRegisterHook: TypeAlias = Callable[[str, "Tool", "ToolRegistry"], "str | None"]
"""Hook called after a tool is added to the registry.

Args:
    tool_name: The name under which the tool was registered.
    tool: The :class:`~toolregistry.tool.Tool` instance that was registered.
    registry: The :class:`~toolregistry.tool_registry.ToolRegistry` that owns it.

Returns:
    A non-empty string to auto-disable the tool with that string as the
    reason, or ``None`` to leave the tool enabled.
"""


@dataclass(frozen=True)
class RefreshResult:
    """Result of a remote source refresh operation.

    Attributes:
        source: Source type that was refreshed (``"openapi"`` or ``"mcp"``).
        source_detail: Transport URI or spec URL identifying the source.
        added: Names of newly discovered tools.
        removed: Names of tools that no longer exist on the remote source.
        updated: Names of tools whose schema or description changed.
        breaking: Subset of *updated* classified as breaking changes.
        compatible: Subset of *updated* classified as compatible changes.
        unchanged: Count of tools that matched and required no update.
        skipped: ``True`` when the remote source reported no changes
            (e.g. HTTP 304 via ETag).
    """

    source: str
    source_detail: str = ""
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    updated: tuple[str, ...] = ()
    breaking: tuple[str, ...] = ()
    compatible: tuple[str, ...] = ()
    unchanged: int = 0
    skipped: bool = False

    @property
    def changed(self) -> bool:
        """Whether the refresh produced any additions, removals, or updates."""
        return bool(self.added or self.removed or self.updated)
