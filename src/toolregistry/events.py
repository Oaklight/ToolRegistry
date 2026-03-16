"""Event types and data classes for ToolRegistry change notifications.

This module provides the event infrastructure for the callback mechanism,
enabling subscribers to receive notifications when tool state changes occur.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeAlias
from collections.abc import Callable


class ChangeEventType(str, Enum):
    """Types of change events that can occur in ToolRegistry.

    Attributes:
        REGISTER: A tool was registered.
        UNREGISTER: A tool was unregistered.
        ENABLE: A tool was enabled.
        DISABLE: A tool was disabled.
        REFRESH: A single tool was refreshed.
        REFRESH_ALL: All tools were refreshed/reloaded.
    """

    REGISTER = "register"
    UNREGISTER = "unregister"
    ENABLE = "enable"
    DISABLE = "disable"
    REFRESH = "refresh"
    REFRESH_ALL = "refresh_all"


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
