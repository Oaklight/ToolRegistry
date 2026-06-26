"""Shared helpers for executor backends — zero toolregistry imports."""

from __future__ import annotations

import inspect
from collections.abc import Callable

from ._types import ExecutionContext


def _unwrap_fn(fn: Callable) -> Callable:
    """Unwrap a tool wrapper to get the underlying function.

    Looks for a ``.fn`` attribute (used by ``_FunctionToolWrapper`` and
    similar wrappers) without importing any toolregistry types.
    """
    return getattr(fn, "fn", fn)


def should_inject_context(fn: Callable) -> bool:
    """Check if ``fn`` has a parameter named ``_ctx`` for context injection.

    If *fn* is a tool wrapper with a ``.fn`` attribute, the inner
    function's signature is inspected instead.

    Args:
        fn: The callable to inspect.

    Returns:
        True if the function accepts a ``_ctx`` parameter typed as
        (or compatible with) ``ExecutionContext``.
    """
    try:
        fn = _unwrap_fn(fn)
        sig = inspect.signature(fn)
        if "_ctx" not in sig.parameters:
            return False
        param = sig.parameters["_ctx"]
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            return True  # name match is sufficient if untyped
        if annotation is ExecutionContext:
            return True
        # Handle string annotations (from __future__ import annotations)
        if isinstance(annotation, str) and "ExecutionContext" in annotation:
            return True
        return False
    except (ValueError, TypeError):
        return False
