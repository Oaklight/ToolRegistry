"""Change callback mixin for ToolRegistry."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, cast

from ..events import ChangeCallback, ChangeEvent, PostRegisterHook

if TYPE_CHECKING:
    from ..tool import Tool
    from ..tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ChangeCallbackMixin:
    """Mixin providing change event callback registration and emission."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._change_callbacks: list[ChangeCallback] = []
        self._callback_lock = threading.Lock()
        self._post_register_hooks: list[PostRegisterHook] = []
        self._hooks_lock = threading.Lock()

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

    def add_post_register_hook(self, hook: PostRegisterHook) -> None:
        """Register a hook to be called after each tool is added to the registry.

        Hooks are invoked synchronously in registration order immediately after
        a tool is inserted into the registry (before the REGISTER change event
        is emitted).  If a hook returns a non-empty string the tool is
        auto-disabled with that string as the reason.  Returning ``None`` leaves
        the tool enabled.

        Args:
            hook: Callable with signature
                ``(tool_name: str, tool: Tool, registry: ToolRegistry) -> str | None``.
                Must not raise exceptions that should propagate; any exception
                is caught and logged.

        Note:
            - Hooks are invoked in registration order.
            - The same hook can be registered multiple times.
            - Hooks should be lightweight; heavy processing should be
              offloaded to a separate thread/task.

        Example:
            ```python
            def my_hook(name: str, tool: Tool, registry: ToolRegistry) -> str | None:
                if name.startswith("dangerous_"):
                    return "Blocked by policy"
                return None

            registry.add_post_register_hook(my_hook)
            ```
        """
        with self._hooks_lock:
            self._post_register_hooks.append(hook)

    def _run_post_register_hooks(self, tool_name: str, tool: Tool) -> None:
        """Invoke all registered post-register hooks for a newly added tool.

        Each hook is called with ``(tool_name, tool, self)``.  If a hook
        returns a non-empty string the tool is auto-disabled.  Exceptions
        raised inside hooks are caught and logged so they never propagate.

        Args:
            tool_name: The name under which the tool was registered.
            tool: The :class:`~toolregistry.tool.Tool` instance that was added.
        """
        with self._hooks_lock:
            hooks = self._post_register_hooks.copy()

        for hook in hooks:
            try:
                result = hook(tool_name, tool, cast("ToolRegistry", self))
            except Exception as exc:
                logger.warning(f"Post-register hook {hook!r} raised exception: {exc}")
                continue

            if result:
                # Non-empty string → auto-disable
                try:
                    cast("ToolRegistry", self).disable(tool_name, reason=result)
                except Exception as exc:
                    logger.warning(
                        f"Auto-disable triggered by post-register hook {hook!r} "
                        f"failed for tool '{tool_name}': {exc}"
                    )
