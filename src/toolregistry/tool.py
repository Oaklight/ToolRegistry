import inspect
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from .parameter_models import _generate_parameters_model


class Tool(BaseModel):
    """Base class representing an executable tool/function.

    Provides core functionality for:
        - Function wrapping and metadata management
        - Parameter validation using Pydantic
        - Synchronous/asynchronous execution
        - JSON schema generation

    Attributes:
        name (str): Name of the tool.
        description (str): Description of tool functionality.
        parameters (Dict[str, Any]): JSON schema for tool parameters.
        callable (Callable[..., Any]): The wrapped callable function.
        is_async (bool): Whether tool supports async execution.
        parameters_model (Optional[Any]): Pydantic model for parameter validation.
    """

    name: str = Field(description="Name of the tool")
    description: str = Field(description="Description of what the tool does")
    parameters: Dict[str, Any] = Field(description="JSON schema for tool parameters")
    callable: Callable[..., Any] = Field(exclude=True)
    is_async: bool = Field(default=False, description="Whether the tool is async")
    parameters_model: Optional[Any] = Field(
        default=None, description="Pydantic Model for tool parameters"
    )

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> "Tool":
        """Factory method to create Tool from callable.

        Automatically:
            - Extracts function metadata
            - Generates parameter schema
            - Handles async/sync detection

        Args:
            func (Callable[..., Any]): Function to convert to tool.
            name (Optional[str]): Override tool name (defaults to function name).
            description (Optional[str]): Override description (defaults to docstring).

        Returns:
            Tool: Configured Tool instance.

        Raises:
            ValueError: For unnamed lambda functions.
        """
        func_name = name or func.__name__

        if func_name == "<lambda>":
            raise ValueError("You must provide a name for lambda functions")

        func_doc = description or func.__doc__ or ""
        is_async = inspect.iscoroutinefunction(func)

        parameters_model = None
        try:
            parameters_model = _generate_parameters_model(func)
        except Exception:
            parameters_model = None
        parameters_schema = (
            parameters_model.model_json_schema() if parameters_model else {}
        )
        return cls(
            name=func_name,
            description=func_doc,
            parameters=parameters_schema,
            callable=func,
            is_async=is_async,
            parameters_model=parameters_model if parameters_model is not None else None,
        )

    def get_json_schema(self) -> Dict[str, Any]:
        """Generate JSON Schema representation of tool.

        Schema includes:
            - Name and description
            - Parameter definitions
            - Async flag

        Returns:
            Dict[str, Any]: JSON Schema compliant tool definition.
        """

        description_json = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
                "is_async": self.is_async,
            },
        }

        return description_json

    describe = get_json_schema
    """Alias for get_json_schema.

    :return: JSON schema representation of the tool
    :rtype: Dict[str, Any]
    """

    def _validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parameters against tool schema.

        Uses Pydantic model if available, otherwise performs basic validation.

        Args:
            parameters (Dict[str, Any]): Raw input parameters.

        Returns:
            Dict[str, Any]: Validated and normalized parameters.
        """
        if self.parameters_model is None:
            validated_params = parameters
        else:
            model = self.parameters_model(**parameters)
            validated_params = model.model_dump_one_level()
        return validated_params

    def run(self, parameters: Dict[str, Any]) -> Any:
        """Execute tool synchronously.

        Args:
            parameters (Dict[str, Any]): Validated input parameters.

        Returns:
            Any: Tool execution result.

        Raises:
            Exception: On execution failure.
        """
        try:
            validated_params = self._validate_parameters(parameters)
            return self.callable(**validated_params)
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"

    async def arun(self, parameters: Dict[str, Any]) -> Any:
        """Execute tool asynchronously.

        Args:
            parameters (Dict[str, Any]): Validated input parameters.

        Returns:
            Any: Tool execution result.

        Raises:
            NotImplementedError: If async execution unsupported.
            Exception: On execution failure.
        """
        try:
            validated_params = self._validate_parameters(parameters)

            if inspect.iscoroutinefunction(self.callable):
                return await self.callable(**validated_params)
            elif hasattr(self.callable, "__call__"):
                return await self.callable(**validated_params)
            raise NotImplementedError(
                "Async execution requires either an async function (coroutine) "
                "or a callable whose __call__ method is async or returns an awaitable object."
            )
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"
