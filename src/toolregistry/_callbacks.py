"""Change callback mixin for ToolRegistry."""

from __future__ import annotations

import logging
import threading

from .events import ChangeCallback, ChangeEvent

logger = logging.getLogger(__name__)


class ChangeCallbackMixin:
    """Mixin providing change event callback registration and emission."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._change_callbacks: list[ChangeCallback] = []
        self._callback_lock = threading.Lock()

    def on_change(self, callback: ChangeCallback) -> None:
        """Register a callback to be notified of tool state changes.

        The callback will be invoked synchronously whenever a tool is
        registered, unregistered, enabled, or disabled.

        Args:
            callback: Function that accepts a ChangeEvent parameter.
                     Must not raise exceptions that should propagate.

        Note:
            - Callbacks are invoked in registration order.
            - The same callback can be registered multiple times.
            - Callbacks should be lightweight; heavy processing should
              be offloaded to a separate thread/task.

        Example:
            ```python
            def my_handler(event: ChangeEvent) -> None:
                print(f"{event.event_type}: {event.tool_name}")
            registry.on_change(my_handler)
            ```
        """
        with self._callback_lock:
            self._change_callbacks.append(callback)

    def remove_on_change(self, callback: ChangeCallback) -> bool:
        """Remove a previously registered callback.

        Args:
            callback: The exact callback function to remove.

        Returns:
            True if the callback was found and removed, False otherwise.

        Note:
            If the same callback was registered multiple times,
            only the first occurrence is removed.

        Example:
            ```python
            registry.remove_on_change(my_handler)  # True
            ```
        """
        with self._callback_lock:
            try:
                self._change_callbacks.remove(callback)
                return True
            except ValueError:
                return False

    def _emit_change(self, event: ChangeEvent) -> None:
        """Notify all registered callbacks of a change event.

        Callbacks are invoked synchronously in registration order.
        Exceptions in callbacks are logged but do not propagate.

        Args:
            event: The change event to emit.
        """
        # Copy callback list to allow modification during iteration
        with self._callback_lock:
            callbacks = self._change_callbacks.copy()

        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                # Log but don't propagate - one bad callback shouldn't
                # break the entire notification chain
                logger.warning(f"Change callback {callback!r} raised exception: {e}")
