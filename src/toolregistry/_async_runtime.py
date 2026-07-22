"""Shared async runtime for all sync→async bridging.

A single daemon thread runs an event loop that stays alive for
the process lifetime.  All async operations (MCP registration,
tool calls, OpenAPI registration) run on this shared loop,
preventing the anyio state pollution that occurs when event loops
are created and destroyed per call (#217).
"""

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


class AsyncRuntime:
    """Process-wide async runtime backed by a persistent daemon thread.

    The loop is lazily created on first use and stays alive until
    :meth:`shutdown` is called.  Thread-safe: concurrent callers
    will not create duplicate loops.
    """

    _loop: asyncio.AbstractEventLoop | None = None
    _thread: threading.Thread | None = None
    _lock = threading.Lock()

    @classmethod
    def get_loop(cls) -> asyncio.AbstractEventLoop:
        """Return the shared event loop, starting it if necessary.

        Returns:
            The persistent event loop running in the daemon thread.
        """
        if cls._loop is not None and cls._loop.is_running():
            return cls._loop

        with cls._lock:
            if cls._loop is not None and cls._loop.is_running():
                return cls._loop

            loop = asyncio.new_event_loop()

            def _run() -> None:
                asyncio.set_event_loop(loop)
                loop.run_forever()

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            cls._loop = loop
            cls._thread = t
            return loop

    @classmethod
    def run_sync(cls, coro: "Coroutine[Any, Any, T]") -> T:
        """Run an async coroutine synchronously on the shared loop.

        Blocks the calling thread until the coroutine completes.

        Args:
            coro: The coroutine to execute.

        Returns:
            The coroutine's return value.
        """
        loop = cls.get_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    @classmethod
    def shutdown(cls) -> None:
        """Stop the shared event loop and join the daemon thread.

        Safe to call multiple times or when no loop was started.
        After shutdown, the next :meth:`get_loop` or :meth:`run_sync`
        call will start a fresh loop.
        """
        with cls._lock:
            loop = cls._loop
            thread = cls._thread
            if loop is not None and loop.is_running():
                loop.call_soon_threadsafe(loop.stop)
            if thread is not None:
                thread.join(timeout=5)
            cls._loop = None
            cls._thread = None
