import asyncio
import inspect
from abc import ABC, abstractmethod
from typing import Any
from collections.abc import Callable


class BaseToolWrapper(ABC):
    """Base class for tool wrappers that provide sync/async transparent calls.

    Every ``Tool.callable`` is a ``BaseToolWrapper`` subclass.  This
    guarantees that ``call_sync()`` and ``call_async()`` are always
    available regardless of the tool's origin (native function, MCP,
    OpenAPI, LangChain).

    Attributes:
        name: Name of the tool.
        params: List of parameter names, default is None.
    """

    def __init__(self, name: str, params: list[str] | None = None) -> None:
        """Initialize the base tool wrapper.

        Args:
            name: Name of the tool.
            params: List of parameter names, default is None.
        """
        self.name = name
        self.params = params

    def _process_args(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Process positional and keyword arguments into a kwargs dict.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Merged keyword arguments dict.

        Raises:
            ValueError: If tool parameters are not initialized.
            TypeError: If invalid or duplicate arguments are provided.
        """
        if args:
            if not self.params:
                raise ValueError("Tool parameters are not initialized.")
            if len(args) > len(self.params):
                raise TypeError(
                    f"Expected at most {len(self.params)} positional arguments, "
                    f"but got {len(args)}."
                )
            for i, arg in enumerate(args):
                param_name = self.params[i]
                if param_name in kwargs:
                    raise TypeError(
                        f"The parameter '{param_name}' was passed as both a positional "
                        f"and a keyword argument."
                    )
                kwargs[param_name] = arg
        return kwargs

    @abstractmethod
    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronous call implementation.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            The result of the call.
        """
        ...

    @abstractmethod
    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Asynchronous call implementation.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            The result of the call.
        """
        ...

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Make the wrapper callable, selecting sync or async automatically.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            The result of the call (or a coroutine if in async context).
        """
        try:
            asyncio.get_running_loop()
            return self.call_async(*args, **kwargs)
        except RuntimeError:
            return self.call_sync(*args, **kwargs)


class _FunctionToolWrapper(BaseToolWrapper):
    """Wrapper for native Python functions (sync or async).

    Created automatically by ``Tool.from_function()`` so that
    ``Tool.callable`` is always a ``BaseToolWrapper``.  The underlying
    function is accessible via the ``.fn`` attribute.

    Args:
        fn: The Python function to wrap.
        name: Tool name.
        params: List of parameter names.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        name: str,
        params: list[str] | None = None,
    ) -> None:
        super().__init__(name, params)
        self.fn = fn
        self._is_async = inspect.iscoroutinefunction(fn)

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the function synchronously.

        Sync functions are called directly.  Async functions are run
        via ``asyncio.run()``.

        Raises:
            RuntimeError: If called from within a running event loop
                with an async function.  Use ``call_async()`` instead.
        """
        kwargs = self._process_args(*args, **kwargs)
        if self._is_async:
            return asyncio.run(self.fn(**kwargs))
        return self.fn(**kwargs)

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the function asynchronously.

        Async functions are awaited directly.  Sync functions are
        dispatched via ``asyncio.to_thread()`` to avoid blocking
        the event loop.
        """
        kwargs = self._process_args(*args, **kwargs)
        if self._is_async:
            return await self.fn(**kwargs)
        return await asyncio.to_thread(self.fn, **kwargs)
