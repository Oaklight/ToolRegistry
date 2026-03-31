"""Shared helpers for executor backends — zero toolregistry imports."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable

from ._types import ExecutionContext


def make_sync_wrapper(async_func: Callable) -> Callable:
    """Wrap an async function so it can be called synchronously.

    Args:
        async_func: An async callable to wrap.

    Returns:
        A synchronous wrapper that runs the async function.
    """

    def wrapper(*args, **kwargs):  # noqa: ANN002, ANN003
        try:
            asyncio.get_running_loop()
            return asyncio.get_event_loop().run_until_complete(
                async_func(*args, **kwargs)
            )
        except RuntimeError:
            return asyncio.run(async_func(*args, **kwargs))

    return wrapper


def should_inject_context(fn: Callable) -> bool:
    """Check if ``fn`` has a parameter named ``_ctx`` for context injection.

    Args:
        fn: The callable to inspect.

    Returns:
        True if the function accepts a ``_ctx`` parameter typed as
        (or compatible with) ``ExecutionContext``.
    """
    try:
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
