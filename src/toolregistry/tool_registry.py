import inspect
import json
from pprint import pprint
from typing import Annotated, Any, Callable, Dict, ForwardRef, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, create_model
from pydantic._internal._typing_extra import eval_type_backport
from pydantic.fields import FieldInfo


class InvalidSignature(Exception):
    """Invalid signature for use with FastMCP."""


class ArgModelBase(BaseModel):
    """A model representing the arguments to a function.

    Features:
    - Supports arbitrary types in fields.
    - Provides a method to dump fields one level deep.
    """

    def model_dump_one_level(self) -> Dict[str, Any]:
        """Dump model fields one level deep, keeping sub-models as-is."""
        return {field: getattr(self, field) for field in self.__pydantic_fields__}

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


def _get_typed_annotation(annotation: Any, globalns: dict[str, Any]) -> Any:
    def try_eval_type(
        value: Any, globalns: dict[str, Any], localns: dict[str, Any]
    ) -> tuple[Any, bool]:
        try:
            return eval_type_backport(value, globalns, localns), True
        except NameError:
            return value, False

    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)
        annotation, status = try_eval_type(annotation, globalns, globalns)

        # This check and raise could perhaps be skipped, and we (FastMCP) just call
        # model_rebuild right before using it 🤷
        if status is False:
            raise InvalidSignature(f"Unable to evaluate type annotation {annotation}")

    return annotation


def _create_field(
    param: inspect.Parameter, annotation_type: Any
) -> tuple[Any, FieldInfo]:
    """
    Create a Pydantic field for a function parameter.

    Args:
        param (inspect.Parameter): The parameter to create a field for.
        annotation_type (Any): The type annotation for the parameter.

    Returns:
        tuple[Any, FieldInfo]: A tuple of the annotated type and the field info.
    """
    default = param.default if param.default is not inspect.Parameter.empty else None
    if param.default is inspect.Parameter.empty:
        field_info = (
            Field(title=param.name)
            if param.annotation is inspect.Parameter.empty
            else Field()
        )
        return (annotation_type, field_info)
    else:
        field_info = (
            Field(default=default, title=param.name)
            if param.annotation is inspect.Parameter.empty
            else Field(default=default)
        )
        return (Optional[annotation_type], field_info)


def _generate_parameters_model(func: Callable) -> Optional[type[ArgModelBase]]:
    """
    Generate a JSON Schema-compliant schema for the function's parameters.

    Args:
        func (Callable): The function to generate the schema for.

    Returns:
        Optional[type[ArgModelBase]]: The Pydantic model representing the function's parameters,
        or None if an error occurs.
    """
    try:
        signature = inspect.signature(func)
        globalns = getattr(func, "__globals__", {})
        dynamic_model_creation_dict: Dict[str, Any] = {}

        for param in signature.parameters.values():
            if param.name == "self":
                continue

            annotation = _get_typed_annotation(param.annotation, globalns)
            if param.annotation is inspect.Parameter.empty:
                dynamic_model_creation_dict[param.name] = _create_field(param, Any)
            elif param.annotation is None:
                dynamic_model_creation_dict[param.name] = _create_field(param, None)
            else:
                dynamic_model_creation_dict[param.name] = _create_field(
                    param, annotation
                )

        return create_model(
            f"{func.__name__}Parameters",
            **dynamic_model_creation_dict,
            __base__=ArgModelBase,
        )
    except Exception as e:
        return None


class Tool(BaseModel):
    """
    Represents a tool (function) that can be called by the language model.
    """

    name: str = Field(description="Name of the tool")
    description: str = Field(description="Description of what the tool does")
    parameters: Dict[str, Any] = Field(description="JSON schema for tool parameters")
    callable: Callable[..., Any] = Field(exclude=True)
    is_async: bool = Field(default=False, description="Whether the tool is async")
    parameters_model: Optional[Annotated[type[ArgModelBase], WithJsonSchema(None)]] = (
        Field(default=None, description="Pydantic Model for tool parameters")
    )

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> "Tool":
        """Create a Tool from a function."""
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

    def run(self, parameters: Dict[str, Any]) -> Any:
        """Run the tool with the given parameters."""
        try:
            if self.parameters_model is None:
                # Directly call the function if no parameters model is defined
                result = self.callable(**parameters)
            else:
                # Convert parameters to model instance for validation
                model = self.parameters_model(**parameters)
                # Call the underlying function with validated parameters
                result = self.callable(**model.model_dump_one_level())
            return f"{self.name} -> {result}"
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"

    async def arun(self, parameters: Dict[str, Any]) -> Any:
        """Async run the tool with the given parameters."""
        try:
            if self.parameters_model is None:
                # Directly call the async function if no parameters model is defined
                if inspect.iscoroutinefunction(self.callable):
                    result = await self.callable(**parameters)
                elif hasattr(self.callable, "__acall__"):
                    result = await self.callable.__acall__(**parameters)
                else:
                    raise NotImplementedError(
                        "Async execution requires either __acall__ implementation "
                        "or the callable to be a coroutine function"
                    )
            else:
                # Convert parameters to model instance for validation
                model = self.parameters_model(**parameters)
                # Call the underlying async function with validated parameters
                if inspect.iscoroutinefunction(self.callable):
                    result = await self.callable(**model.model_dump_one_level())
                elif hasattr(self.callable, "__acall__"):
                    result = await self.callable.__acall__(
                        **model.model_dump_one_level()
                    )
                else:
                    raise NotImplementedError(
                        "Async execution requires either __acall__ implementation "
                        "or the callable to be a coroutine function"
                    )
            return f"{self.name} -> {result}"
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"


class ToolRegistry:
    """
    A registry for managing tools (functions) and their metadata.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """
        Check if a tool with the given name is registered.
        """
        return name in self._tools

    def register(
        self, tool_or_func: Union[Callable, Tool], description: Optional[str] = None
    ):
        """
        Register a tool, either as a function or Tool instance.

        Args:
            tool_or_func (Union[Callable, Tool]): The tool to register, either as a function or Tool instance.
            description (str, optional): Description for function tools. If not provided,
                                       the function's docstring will be used.
        """
        if isinstance(tool_or_func, Tool):
            self._tools[tool_or_func.name] = tool_or_func
        else:
            tool = Tool.from_function(tool_or_func, description=description)
            self._tools[tool.name] = tool

    def merge(self, other: "ToolRegistry", keep_existing: bool = False):
        """
        Merge tools from another ToolRegistry into this one.

        Args:
            other (ToolRegistry): The other ToolRegistry to merge into this one.
        """
        if not isinstance(other, ToolRegistry):
            raise TypeError("Can only merge with another ToolRegistry instance.")

        if keep_existing:
            for name, tool in other._tools.items():
                if name not in self._tools:
                    self._tools[name] = tool
        else:
            self._tools.update(other._tools)

    def register_mcp_tools(self, server_url: str):
        """
        Register all tools from an MCP server (synchronous entry point).
        Requires the [mcp] extra to be installed.

        Args:
            server_url (str): URL of the MCP server
        """
        try:
            from .mcp_integration import MCPIntegration

            mcp = MCPIntegration(self)
            return mcp.register_mcp_tools(server_url)
        except ImportError:
            raise ImportError(
                "MCP integration requires the [mcp] extra. "
                "Install with: pip install toolregistry[mcp]"
            )

    async def register_mcp_tools_async(self, server_url: str):
        """
        Async implementation to register all tools from an MCP server.
        Requires the [mcp] extra to be installed.

        Args:
            server_url (str): URL of the MCP server
        """
        try:
            from .mcp_integration import MCPIntegration

            mcp = MCPIntegration(self)
            return await mcp.register_mcp_tools_async(server_url)
        except ImportError:
            raise ImportError(
                "MCP integration requires the [mcp] extra. "
                "Install with: pip install toolregistry[mcp]"
            )

    def get_tools_json(self) -> List[Dict[str, Any]]:
        """
        Get the JSON representation of all registered tools, following JSON Schema.

        Returns:
            List[Dict[str, Any]]: A list of tools in JSON format, compliant with JSON Schema.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "is_async": tool.is_async,
                },
            }
            for tool in self._tools.values()
        ]

    def get_callable(self, function_name: str) -> Optional[Callable[..., Any]]:
        """
        Get a callable function by its name.

        Args:
            function_name (str): The name of the function.

        Returns:
            Callable: The function to call, or None if not found.
        """
        tool = self._tools.get(function_name)
        return tool.callable if tool else None

    def execute_tool_calls(self, tool_calls: List[Any]) -> Dict[str, str]:
        """
        Execute tool calls by delegating to each Tool's run method. Uses parallel execution
        for multiple tool calls and sequential execution for less than 3 tool calls to avoid
        thread pool overhead.

        Args:
            tool_calls (List[Any]): List of tool calls

        Returns:
            Dict[str, str]: Dictionary mapping tool call IDs to results
        """

        def process_tool_call(tool_call):
            try:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                tool_call_id = tool_call.id

                # Get the tool from registry
                tool = self._tools.get(function_name)
                if tool:
                    tool_result = tool.run(function_args)
                else:
                    tool_result = f"Error: Tool '{function_name}' not found"
            except Exception as e:
                tool_result = f"Error executing {function_name}: {str(e)}"
            return (tool_call_id, tool_result)

        tool_responses = {}

        if len(tool_calls) > 2:
            # only use concurrency if more than 2 tool calls at a time
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(process_tool_call, tool_call)
                    for tool_call in tool_calls
                ]
                for future in concurrent.futures.as_completed(futures):
                    tool_call_id, tool_result = future.result()
                    tool_responses[tool_call_id] = tool_result
        else:
            for tool_call in tool_calls:
                tool_call_id, tool_result = process_tool_call(tool_call)
                tool_responses[tool_call_id] = tool_result

        return tool_responses

    def recover_tool_call_assistant_message(
        self, tool_calls: List[Any], tool_responses: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Construct assistant messages with tool call results.

        Args:
            tool_calls (List[Any]): List of tool calls
            tool_responses (Dict[str, str]): Tool execution results

        Returns:
            List[Dict[str, Any]]: List of message dictionaries
        """
        messages = []
        for tool_call in tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "content": tool_responses[tool_call.id],
                    "tool_call_id": tool_call.id,
                }
            )
        return messages

    def __repr__(self):
        """
        Return the JSON representation of the registry for debugging purposes.
        """
        return json.dumps(self.get_tools_json(), indent=2)

    def __str__(self):
        """
        Return the JSON representation of the registry as a string.
        """
        return json.dumps(self.get_tools_json(), indent=2)

    def __getitem__(self, key: str) -> Optional[Callable[..., Any]]:
        """
        Enable key-value access to retrieve callables.

        Args:
            key (str): The name of the function.

        Returns:
            Optional[Callable[..., Any]]: The function to call, or None if not found.
        """
        return self.get_callable(key)
