"""PTC (Programmatic Tool Calling) protocols and core types.

This module defines the abstractions for executing LLM-generated code
with tool access.  It has **zero imports from toolregistry internals**
(same constraint as ``executor/``).

Protocols
---------
- :class:`ToolProjection` — how a tool appears inside a code runtime's
  namespace (callable with name and docstring).
- :class:`CodeRuntime` — executes code strings with tool access and
  returns structured results.

Concrete implementations
------------------------
- :class:`DirectProjection` — in-process wrapper around a bare callable.
  Used by ``InProcessRuntime`` (issue #176).
- ``StubProjection`` — IPC stub for subprocess isolation (issue #177,
  not yet implemented).

Result types
------------
- :class:`CodeResult` — structured output from code execution.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from collections.abc import Callable


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CodeResult:
    """Structured result from code execution in a :class:`CodeRuntime`.

    Attributes:
        stdout: Captured standard output from the executed code.
        stderr: Content the code wrote to standard error during execution.
        return_code: ``0`` for success, ``1`` for exception.  In-process
            runtimes use this convention since there is no real OS exit
            code.
        error: Exception traceback that terminated execution, or ``None``
            if the code completed successfully.  Distinct from *stderr*,
            which captures intentional writes to ``sys.stderr``.
    """

    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    error: str | None = None


# ---------------------------------------------------------------------------
# ToolProjection protocol + DirectProjection
# ---------------------------------------------------------------------------


@runtime_checkable
class ToolProjection(Protocol):
    """How a tool appears inside a code runtime's namespace.

    In-process runtimes use :class:`DirectProjection` (zero overhead).
    Isolated runtimes (subprocess, container) will use IPC stubs that
    satisfy the same interface.

    The ``__call__`` method is synchronous — runtimes that need async
    dispatch handle the wrapping themselves.
    """

    @property
    def name(self) -> str:
        """Tool name as it appears in the code namespace."""
        ...

    @property
    def doc(self) -> str | None:
        """Docstring shown to the LLM-generated code (e.g. via ``help()``)."""
        ...

    def __call__(self, **kwargs: Any) -> Any:
        """Invoke the tool with keyword arguments."""
        ...


class DirectProjection:
    """In-process :class:`ToolProjection` — wraps a callable with zero overhead.

    Used by ``InProcessRuntime`` (issue #176).  Takes a bare callable
    plus metadata — no dependency on ``Tool`` or any toolregistry type.
    The caller who has access to a ``Tool`` object constructs this::

        proj = DirectProjection(
            name=tool.name,
            fn=tool.fn,
            doc=tool.description,
        )

    For ``SubprocessRuntime`` (issue #177), a ``StubProjection`` will be
    added that serializes calls over IPC behind the same interface.

    Attributes:
        fn: The underlying callable (sync or async).
    """

    def __init__(
        self,
        name: str,
        fn: Callable[..., Any],
        doc: str | None = None,
    ) -> None:
        self._name = name
        self.fn = fn
        self._doc = doc
        self._is_async = inspect.iscoroutinefunction(fn)

    @property
    def name(self) -> str:
        """Tool name as it appears in the code namespace."""
        return self._name

    @property
    def doc(self) -> str | None:
        """Docstring for the tool."""
        return self._doc

    def __call__(self, **kwargs: Any) -> Any:
        """Invoke the tool synchronously.

        Async callables are run via ``asyncio.run()``.  This is
        appropriate for in-process ``exec()`` contexts where the code
        runs synchronously.

        Note:
            ``asyncio.run()`` cannot be called from within a running
            event loop.  If the ``CodeRuntime.execute()`` implementation
            itself runs inside an event loop, it must handle this — e.g.
            by running ``exec()`` in a separate thread via
            ``asyncio.to_thread()``.  See issue #176.
        """
        if self._is_async:
            return asyncio.run(self.fn(**kwargs))
        return self.fn(**kwargs)


# ---------------------------------------------------------------------------
# Namespace helpers
# ---------------------------------------------------------------------------


def validate_namespace(namespace: dict[str, ToolProjection]) -> None:
    """Check that each key matches its ``ToolProjection.name``.

    Raises:
        ValueError: If any key/name pair is inconsistent.
    """
    for key, proj in namespace.items():
        if key != proj.name:
            raise ValueError(
                f"Namespace key {key!r} does not match "
                f"ToolProjection.name {proj.name!r}"
            )


# ---------------------------------------------------------------------------
# CodeRuntime protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class CodeRuntime(Protocol):
    """Executes LLM-generated code with tool access.

    Different from ``ExecutionBackend``:

    ============  =======================================
    CodeRuntime   code string + tool namespace → result
                  bidirectional, multi-call
    ExecutionBackend  single callable + kwargs → result
                  unidirectional, one-shot
    ============  =======================================

    CodeRuntime is a *consumer* of ExecutionBackend, not a replacement.
    """

    async def execute(
        self,
        code: str,
        namespace: dict[str, ToolProjection],
        *,
        timeout: float | None = None,
        extra_globals: dict[str, Any] | None = None,
    ) -> CodeResult:
        """Execute *code* with tools from *namespace*.

        Args:
            code: Python source code to execute.
            namespace: Mapping of tool name → :class:`ToolProjection`.
                These are injected into the execution namespace so the
                code can call them directly.
            timeout: Maximum wall-clock seconds.  ``None`` means no limit.
            extra_globals: Additional objects (imports, constants, etc.)
                to inject into the execution namespace alongside tools.
                Tool entries win on name collision.

        Returns:
            A :class:`CodeResult` with captured stdout, stderr, and
            error information.
        """
        ...
