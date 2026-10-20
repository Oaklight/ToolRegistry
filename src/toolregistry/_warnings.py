"""Warning helpers that attribute messages to the caller's frame."""

from __future__ import annotations

import contextvars
import inspect
import sysconfig
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any
from collections.abc import Iterator

__all__ = ["warn_at_user_frame"]

_PACKAGE_ROOT = Path(__file__).resolve().parent
_STDLIB_ROOT = Path(sysconfig.get_paths()["stdlib"]).resolve()


@dataclass(frozen=True)
class _WarningLocation:
    """A captured caller location that can cross a thread boundary."""

    filename: str
    lineno: int
    module: str | None
    module_globals: dict[str, Any] | None


#: Set by AsyncRuntime.run_sync() on the calling thread.  The coroutine
#: inherits the context when scheduled, so warnings emitted on the event
#: loop thread can still point at the synchronous caller.
_sync_caller: contextvars.ContextVar[_WarningLocation | None] = contextvars.ContextVar(
    "toolregistry_sync_caller", default=None
)


def _is_library_frame(frame: FrameType) -> bool:
    """Return whether *frame* belongs to this package or the stdlib.

    Standard-library frames are skipped so that an executor worker (for
    example ``concurrent.futures.thread._worker``) is not reported as the
    warning's source when the real caller is not on the stack.
    """
    try:
        path = Path(frame.f_code.co_filename).resolve()
    except (OSError, ValueError):
        return False
    return path.is_relative_to(_PACKAGE_ROOT) or path.is_relative_to(_STDLIB_ROOT)


def _location(frame: FrameType) -> _WarningLocation:
    return _WarningLocation(
        filename=frame.f_code.co_filename,
        lineno=frame.f_lineno,
        module=frame.f_globals.get("__name__"),
        module_globals=frame.f_globals,
    )


def _nearest_user_location(start: FrameType | None) -> _WarningLocation | None:
    current = start
    while current is not None and _is_library_frame(current):
        current = current.f_back
    return _location(current) if current is not None else None


@contextmanager
def capture_sync_caller() -> Iterator[None]:
    """Carry the synchronous caller's location into a coroutine.

    Must be entered from the synchronous wrapper that is about to hand a
    coroutine to another thread (``AsyncRuntime.run_sync``).  The event-loop
    thread inherits the context, so :func:`warn_at_user_frame` can report
    the caller instead of the bridge.
    """
    frame = inspect.currentframe()
    try:
        location = _nearest_user_location(frame.f_back if frame else None)
    finally:
        del frame

    if location is None:
        yield
        return

    token = _sync_caller.set(location)
    try:
        yield
    finally:
        _sync_caller.reset(token)


def warn_at_user_frame(
    message: str,
    category: type[Warning],
    *,
    fallback_stacklevel: int = 2,
) -> None:
    """Emit a warning pointing at the nearest non-library frame.

    A fixed ``stacklevel`` cannot follow the call stack through the async
    runtime bridge or an executor thread.  This helper walks outwards until
    it leaves both :mod:`toolregistry` and the standard library, then uses
    that frame's depth.

    When the call arrives through ``AsyncRuntime.run_sync``, the location
    captured on the calling thread is used instead; the coroutine runs on
    the event-loop thread, where the user's frames are not reachable.

    When every reachable frame is internal (a warning emitted from a worker
    thread whose caller is not on the stack), attribution falls back to
    *fallback_stacklevel* rather than pointing at interpreter internals.

    Args:
        message: Warning message.  Callers should make it self-contained,
            because the reported location may still be approximate.
        category: Warning category, e.g. :class:`UserWarning`.
        fallback_stacklevel: Depth used when no user frame is reachable.
            ``2`` points at the immediate caller of this helper.

    Warns:
        category: The constructed warning.
    """
    captured = _sync_caller.get()
    if captured is not None:
        # Pass the caller's warning registry rather than its module globals:
        # warn_explicit() with module_globals reaches
        # importlib._bootstrap_external._bless_my_loader, which emits a
        # DeprecationWarning when the caller is a __main__ script without a
        # __spec__.loader.  That doubles the warning and, under -W error,
        # raises DeprecationWarning instead of the intended category.
        registry = (
            captured.module_globals.get("__warningregistry__")
            if captured.module_globals is not None
            else None
        )
        warnings.warn_explicit(
            message,
            category,
            captured.filename,
            captured.lineno,
            module=captured.module,
            registry=registry,
        )
        return

    frame = inspect.currentframe()
    try:
        current: FrameType | None = frame.f_back if frame is not None else None
        # stacklevel=1 is this helper's frame; 2 is its caller.
        stacklevel = 2
        while current is not None and _is_library_frame(current):
            stacklevel += 1
            current = current.f_back
        if current is None:
            stacklevel = fallback_stacklevel
    finally:
        # Drop the reference before emitting so the frame is not kept
        # alive by a traceback if the warning is turned into an error.
        del frame

    warnings.warn(message, category, stacklevel=stacklevel)
