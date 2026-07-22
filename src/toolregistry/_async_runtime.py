"""Shared async runtime for sync→async bridging.

Provides a single persistent event loop on a daemon thread, shared
across all synchronous entry points (MCP registration, OpenAPI
registration, tool calls).  This avoids the create-and-destroy-loop
pattern that breaks ``anyio`` process-level state when multiple async
sources are registered sequentially.

Usage::

    from toolregistry._async_runtime import AsyncRuntime

    result = AsyncRuntime.run_sync(some_coroutine())
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, TypeVar
from collections.abc import Coroutine

T = TypeVar("T")


class AsyncRuntime:
    """Shared async runtime for all sync→async bridging.

    A single daemon thread runs an event loop that stays alive for the
    process lifetime.  All async operations — MCP registration, tool
    calls, OpenAPI registration — run on this shared loop.

    The loop is lazily created on first use and kept alive until
    :meth:`shutdown` is called (or the process exits, since the thread
    is a daemon).
    """

    _loop: asyncio.AbstractEventLoop | None = None
    _thread: threading.Thread | None = None
    _lock = threading.Lock()

    @classmethod
    def get_loop(cls) -> asyncio.AbstractEventLoop:
        """Return the shared event loop, lazily starting it if needed.

        Thread-safe: concurrent callers will not create duplicate loops.

        Returns:
            The persistent event loop running in the daemon thread.
        """
        if cls._loop is not None and cls._loop.is_running():
            return cls._loop

        with cls._lock:
            # Double-check after acquiring lock.
            if cls._loop is not None and cls._loop.is_running():
                return cls._loop

            loop = asyncio.new_event_loop()

            def _run() -> None:
                asyncio.set_event_loop(loop)
                loop.run_forever()

            t = threading.Thread(target=_run, daemon=True, name="async-runtime")
            t.start()
            cls._loop = loop
            cls._thread = t
            return loop

    @classmethod
    def run_sync(cls, coro: Coroutine[Any, Any, T]) -> T:
        """Run an async coroutine synchronously on the shared loop.

        Blocks the calling thread until the coroutine completes.

        Args:
            coro: The coroutine to execute.

        Returns:
            The coroutine's return value.

        Raises:
            Any exception raised by the coroutine.
        """
        loop = cls.get_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    @classmethod
    def shutdown(cls) -> None:
        """Stop the shared event loop and join the daemon thread.

        Safe to call multiple times or when the loop was never started.
        After shutdown, the next :meth:`get_loop` or :meth:`run_sync`
        call will lazily create a new loop.
        """
        with cls._lock:
            loop = cls._loop
            thread = cls._thread
            if loop is not None and loop.is_running():
                loop.call_soon_threadsafe(loop.stop)
            if thread is not None:
                thread.join(timeout=5)
            if loop is not None and not loop.is_closed():
                loop.close()
            cls._loop = None
            cls._thread = None
