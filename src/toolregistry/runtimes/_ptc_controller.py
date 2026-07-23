"""PTC (Programmatic Tool Calling) controller.

Manages the lifecycle of the ``programmatic_tool_call`` tool — enable/disable,
runtime injection, invocation tracking.  Exposed as ``registry.ptc``.

Usage::

    registry.ptc.enable(timeout=30)
    registry.ptc.disable()
    registry.ptc.enabled           # bool
    registry.ptc.last_invocation_id  # str | None
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..tool_registry import ToolRegistry

PTC_TOOL_NAME = "programmatic_tool_call"

PTC_TOOL_DESCRIPTION = (
    "Write Python code to orchestrate multiple tool calls in a single block. "
    "Registered tools are available as callable functions — call them "
    "directly (e.g. ``result = search(query='...')``). "
    "Only print() output is returned to you. "
    "This is NOT a general Python runtime — file I/O, network access, "
    "and unsafe imports are blocked."
)


class PtcController:
    """Controller for Programmatic Tool Calling (PTC).

    Always present on :class:`ToolRegistry` as ``registry.ptc``.
    Call :meth:`enable` to register the ``programmatic_tool_call`` tool;
    call :meth:`disable` to unregister it.

    The controller delegates code execution to a ``codecell``
    runtime (default: ``IpcSubprocessRuntime``).  Tool calls inside
    the executed code go through ``registry.invoke()`` with full
    permission and logging enforcement.

    Args:
        registry: The owning :class:`ToolRegistry` instance.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._executor: Any = None  # PtcTool | None
        self._last_invocation_id: str | None = None

    @property
    def enabled(self) -> bool:
        """Whether PTC is currently enabled."""
        return self._executor is not None

    @property
    def last_invocation_id(self) -> str | None:
        """Invocation ID of the last PTC execution (``tr_ptc_...``).

        Preserved after :meth:`disable` so callers can still query
        the execution log for the last run's tool calls.

        Returns ``None`` if PTC has never been used.
        """
        if self._executor is not None:
            return self._executor.last_invocation_id
        return self._last_invocation_id

    def enable(
        self,
        *,
        timeout: float = 30,
        runtime: Any = None,
    ) -> None:
        """Enable PTC and register the ``programmatic_tool_call`` tool.

        Calling ``enable()`` again while already enabled raises
        ``ValueError``.  Call :meth:`disable` first to reconfigure.

        Args:
            timeout: Default execution timeout in seconds.
            runtime: Optional codecell runtime instance (must implement
                ``BaseRuntime``).  If ``None``, uses
                ``codecell.IpcSubprocessRuntime(PythonValidator())``.

        Raises:
            ValueError: If PTC is already enabled.
            ImportError: If the ``codecell`` package is not installed.
                Install with ``pip install toolregistry[ptc]``.
        """
        if self.enabled:
            raise ValueError(
                "PTC is already enabled. Call registry.ptc.disable() "
                "first to reconfigure."
            )

        from ._ptc_tool import PtcTool
        from ..tool import Tool, ToolMetadata

        executor = PtcTool(
            self._registry,
            timeout=timeout,
            runtime=runtime,
        )

        code_tool = Tool.from_function(
            executor.execute,
            name=PTC_TOOL_NAME,
            description=PTC_TOOL_DESCRIPTION,
            # Must run in the main process: its IPC tool callbacks go
            # through registry.invoke()/_invoke_raw, and it holds a live
            # registry reference that cannot cross a process boundary.
            metadata=ToolMetadata(defer=False, natural_backend="inline"),
        )
        self._registry.register(code_tool)

        self._executor = executor

    def disable(self) -> None:
        """Disable PTC and unregister the ``programmatic_tool_call`` tool.

        The :attr:`last_invocation_id` is preserved after disable
        so callers can still query the execution log.
        """
        if not self.enabled:
            return
        # Preserve last invocation ID before clearing executor
        self._last_invocation_id = self._executor.last_invocation_id
        self._registry._tools.pop(PTC_TOOL_NAME, None)
        self._executor = None
