"""Shared async runtime for all sync→async bridging.

A single daemon thread runs an event loop that stays alive for the
process lifetime.  All async operations (MCP registration, tool calls,
OpenAPI registration) run on this shared loop, avoiding the
create-and-destroy-per-call pattern that breaks anyio resources.
"""

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


class AsyncRuntime:
    """Process-wide persistent event loop for sync→async bridging.

    A daemon thread lazily starts on first use and runs an event loop
    that is never destroyed.  This keeps MCP transports, anyio streams,
    and HTTP connections alive across successive sync calls.

    Thread-safe: concurrent callers will not create duplicate loops.
    """

    _loop: asyncio.AbstractEventLoop | None = None
    _thread: threading.Thread | None = None
    _lock = threading.Lock()

    @classmethod
    def get_loop(cls) -> asyncio.AbstractEventLoop:
        """Return the shared event loop, starting the daemon thread if needed.

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
    def run_sync(cls, coro: Coroutine[Any, Any, T]) -> T:
        """Run an async coroutine synchronously on the shared loop.

        Blocks the calling thread until the coroutine completes.

        Args:
            coro: The coroutine to run.

        Returns:
            The coroutine's return value.

        Raises:
            Any exception raised by the coroutine.
        """
        loop = cls.get_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    @classmethod
    def shutdown(cls) -> None:
        """Stop the shared loop and join the daemon thread.

        Intended for test teardown or explicit process cleanup.
        Normal usage does not require calling this — the daemon thread
        exits automatically when the process ends.
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
