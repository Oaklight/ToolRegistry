import inspect
from typing import Any, Callable, Dict, Literal, Optional

from pydantic import BaseModel, Field

from .parameter_models import _generate_parameters_model
from .utils import normalize_tool_name


class Tool(BaseModel):
    """Base class representing an executable tool/function.

    Provides core functionality for:
        - Function wrapping and metadata management
        - Parameter validation using Pydantic
        - Synchronous/asynchronous execution
        - JSON schema generation
    """

    name: str = Field(description="Name of the tool")
    """The name of the tool.
    
    Used as the primary identifier when calling the tool.
    Must be unique within a tool registry.
    """

    description: str = Field(description="Description of what the tool does")
    """Detailed description of the tool's functionality.
    
    Should clearly explain what the tool does, its purpose,
    and any important usage considerations.
    """

    parameters: Dict[str, Any] = Field(description="JSON schema for tool parameters")
    """Parameter schema defining the tool's expected inputs.
    
    Follows JSON Schema format. Automatically generated from
    the wrapped function's type hints when using from_function().
    """

    callable: Callable[..., Any] = Field(exclude=True)
    """The underlying function/method that implements the tool's logic.
    
    This is excluded from serialization to prevent accidental exposure
    of sensitive implementation details.
    """

    is_async: bool = Field(default=False, description="Whether the tool is async")
    """Flag indicating if the tool requires async execution.
    
    Automatically detected from the wrapped function when using
    from_function(). Defaults to False for synchronous tools.
    """

    parameters_model: Optional[Any] = Field(
        default=None, description="Pydantic Model for tool parameters"
    )
    """Pydantic model used for parameter validation.
    
    Automatically generated from the wrapped function's type hints
    when using from_function(). Can be None for tools without
    parameter validation.
    """

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
        namespace: Optional[str] = None,
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

        func_name = normalize_tool_name(func_name)

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
        tool = cls(
            name=func_name,
            description=func_doc,
            parameters=parameters_schema,
            callable=func,
            is_async=is_async,
            parameters_model=parameters_model if parameters_model is not None else None,
        )

        if namespace:
            tool.update_namespace(namespace)

        return tool

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

    def update_namespace(
        self,
        namespace: Optional[str],
        force: bool = False,
        sep: Literal["-", "."] = "-",
    ) -> None:
        """Updates the namespace of a tool.

        This method checks if the tool's name already contains a namespace (indicated by the presence of a separator character).
        OpenAI requires that function names match the pattern ``^[a-zA-Z0-9_-]+$``. Some other providers allow dot (`.`) as separator.
        If it does and `force` is `True`, the existing namespace is replaced with the provided `namespace`.
        If `force` is `False` and an existing namespace is present, no changes are made.
        If the tool's name does not contain a namespace, the `namespace` is prepended as a prefix to the tool's name.

        Args:
            namespace (str): The new namespace to apply to the tool's name.
            force (bool, optional): If `True`, forces the replacement of an existing namespace. Defaults to `False`.

        Returns:
            None: This method modifies the `tool.name` attribute in place and does not return a value.

        Example:
            >>> tool = Tool(name="example_tool")
            >>> tool.update_namespace("new_namespace")
            >>> tool.name
            'new_namespace-example_tool'

            >>> tool = Tool(name="old_namespace.example_tool")
            >>> tool.update_namespace("new_namespace", force=False)
            >>> tool.name
            'old_namespace-example_tool'

            >>> tool = Tool(name="old_namespace.example_tool")
            >>> tool.update_namespace("new_namespace", force=True, sep=".")
            >>> tool.name
            'new_namespace.example_tool'
        """
        if not namespace:
            return

        namespace = normalize_tool_name(namespace)
        if sep in self.name:
            if force:
                # Replace existing namespace with the new one if force is True
                self.name = f"{namespace}{sep}{self.name.split(sep, 1)[1]}"
            else:
                # Do not change the name if force is False and an existing namespace is present
                pass
        else:
            # Add the new namespace as a prefix if there is no existing namespace
            self.name = f"{namespace}{sep}{self.name}"
