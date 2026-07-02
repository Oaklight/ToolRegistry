"""PTC (Programmatic Tool Calling) bridge layer.

This module provides the toolregistry-specific abstractions for PTC:

- :class:`ToolProjection` — how a ``Tool`` appears inside a code
  runtime's namespace (callable with name and docstring).
- :class:`DirectProjection` — in-process wrapper that converts a
  ``Tool`` into a bare callable for codecell.

Code execution itself is delegated to the ``codecell`` package, which
provides ``SubprocessRuntime``, ``CodeResult``, and validators.

This module has **zero imports from toolregistry internals** (same
constraint as ``executor/``).  The caller who has access to ``Tool``
objects constructs ``DirectProjection`` instances.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# ToolProjection protocol + DirectProjection
# ---------------------------------------------------------------------------


@runtime_checkable
class ToolProjection(Protocol):
    """How a tool appears inside a code runtime's namespace.

    ``ToolProjection`` bridges toolregistry's ``Tool`` model into a
    shape that codecell can consume: a callable with a name and
    docstring.

    The ``__call__`` method is synchronous — codecell runtimes handle
    isolation (subprocess, etc.) themselves.
    """

    @property
    def name(self) -> str:
        """Tool name as it appears in the code namespace."""
        ...

    @property
    def doc(self) -> str | None:
        """Docstring shown to the LLM-generated code."""
        ...

    def __call__(self, **kwargs: Any) -> Any:
        """Invoke the tool with keyword arguments."""
        ...


class DirectProjection:
    """In-process :class:`ToolProjection` — wraps a callable with zero overhead.

    Takes a bare callable plus metadata — no dependency on ``Tool`` or
    any toolregistry type.  The caller constructs this from a ``Tool``::

        proj = DirectProjection(
            name=tool.name,
            fn=tool.fn,
            doc=tool.description,
        )

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

        Async callables are run via ``asyncio.run()``.

        Warning:
            ``asyncio.run()`` cannot be called from within a running
            event loop (e.g. Jupyter, FastAPI).  If the caller is
            already in an async context, use ``await proj.fn(**kwargs)``
            directly instead.
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


def namespace_to_callables(
    namespace: dict[str, ToolProjection],
) -> dict[str, Callable[..., Any]]:
    """Convert a ToolProjection namespace to a plain callable dict.

    This is the bridge between toolregistry's ``ToolProjection`` and
    codecell's ``namespace: dict[str, Callable]`` parameter.

    Calls :func:`validate_namespace` first to ensure key/name
    consistency before conversion.

    Note:
        The conversion itself is intentionally trivial
        (``dict(namespace)`` would also work).  The function exists
        to carry the type conversion semantics and the validation
        guarantee: ``ToolProjection`` → validated ``Callable``.

    Args:
        namespace: Mapping of tool name -> ToolProjection.

    Returns:
        Mapping of tool name -> callable (the ToolProjection itself,
        since it implements ``__call__``).

    Raises:
        ValueError: If any key does not match its ToolProjection.name.
    """
    validate_namespace(namespace)
    return {name: proj for name, proj in namespace.items()}
