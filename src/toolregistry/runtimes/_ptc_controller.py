"""PTC (Programmatic Tool Calling) controller.

Manages the lifecycle of the ``code_execution`` tool — enable/disable,
runtime injection, invocation tracking.  Exposed as ``registry.ptc``.

Usage::

    registry.ptc.enable(timeout=30)
    registry.ptc.disable()
    registry.ptc.enabled           # bool
    registry.ptc.last_invocation_id  # str | None
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._code_execution import CODE_EXECUTION_DESCRIPTION, CODE_EXECUTION_NAME

if TYPE_CHECKING:
    from ..tool_registry import ToolRegistry


class PtcController:
    """Controller for Programmatic Tool Calling (PTC).

    Always present on :class:`ToolRegistry` as ``registry.ptc``.
    Call :meth:`enable` to register the ``code_execution`` tool;
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
        self._executor: Any = None  # CodeExecutionTool | None
        self._enabled = False

    @property
    def enabled(self) -> bool:
        """Whether PTC is currently enabled."""
        return self._enabled

    @property
    def last_invocation_id(self) -> str | None:
        """Invocation ID of the last PTC execution (``tr_ptc_...``).

        Returns ``None`` if PTC has not been used or is disabled.
        """
        if self._executor is None:
            return None
        return self._executor.last_invocation_id

    def enable(
        self,
        *,
        timeout: float = 30,
        runtime: Any = None,
    ) -> None:
        """Enable PTC and register the ``code_execution`` tool.

        Args:
            timeout: Default execution timeout in seconds.
            runtime: Optional codecell runtime instance (must implement
                ``BaseRuntime``).  If ``None``, uses
                ``codecell.IpcSubprocessRuntime(PythonValidator())``.

        Raises:
            ImportError: If the ``codecell`` package is not installed.
                Install with ``pip install toolregistry[ptc]``.
        """
        if self._enabled:
            return

        from ._code_execution import CodeExecutionTool
        from ..tool import Tool, ToolMetadata

        executor = CodeExecutionTool(
            self._registry,
            timeout=timeout,
            runtime=runtime,
        )

        code_tool = Tool.from_function(
            executor.execute,
            name=CODE_EXECUTION_NAME,
            description=CODE_EXECUTION_DESCRIPTION,
            metadata=ToolMetadata(defer=False),
        )
        self._registry.register(code_tool)

        self._executor = executor
        self._enabled = True

    def disable(self) -> None:
        """Disable PTC and unregister the ``code_execution`` tool."""
        if not self._enabled:
            return
        self._registry._tools.pop(CODE_EXECUTION_NAME, None)
        self._executor = None
        self._enabled = False
