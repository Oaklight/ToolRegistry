import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseToolWrapper(ABC):
    """Base class for tool wrappers that provide support for synchronous
    and asynchronous calls.

    Attributes:
        name (str): Name of the tool.
        params (Optional[List[str]]): List of parameter names, default is None.
    """

    def __init__(self, name: str, params: Optional[List[str]] = None) -> None:
        """Initializes the base tool wrapper.

        Args:
            name (str): Name of the tool.
            params (Optional[List[str]]): List of parameter names, default is None.
        """
        self.name = name
        self.params = params

    def _process_args(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Processes positional and keyword arguments.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Dict[str, Any]: Dictionary of processed arguments.

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
            Any: The result of the call.

        Raises:
            NotImplementedError: Must be implemented by a subclass.
        """
        raise NotImplementedError(
            "The 'call_sync' method must be implemented by a subclass."
        )

    @abstractmethod
    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Asynchronous call implementation.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Any: The result of the call.

        Raises:
            NotImplementedError: Must be implemented by a subclass.
        """
        raise NotImplementedError(
            "The 'call_async' method must be implemented by a subclass."
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Makes the wrapper callable and automatically selects between
        synchronous and asynchronous versions.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Any: The result of the call.
        """
        try:
            asyncio.get_running_loop()
            return self.call_async(*args, **kwargs)
        except RuntimeError:
            return self.call_sync(*args, **kwargs)
