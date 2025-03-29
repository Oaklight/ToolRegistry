import inspect
import json
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel


class Tool(BaseModel):
    """
    Represents a tool (function) that can be called by the language model.
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    callable: Callable


class ToolRegistry:
    """
    A registry for managing tools (functions) and their metadata.
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def __len__(self):
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """
        Check if a tool with the given name is registered.
        """
        return name in self._tools

    def register(self, func: Callable, description: Optional[str] = None):
        """
        Register a function as a tool.

        Args:
            func (Callable): The function to register.
            description (str, optional): A description of the function. If not provided,
                                        the function's docstring will be used.
        """
        # Generate the function's JSON schema based on its signature
        parameters = self._generate_parameters_schema(func)
        name = func.__name__
        description = description or func.__doc__ or "No description provided."

        # Create a Tool instance
        tool = Tool(
            name=name,
            description=description,
            parameters=parameters,
            callable=func,
        )

        # Add the tool to the registry
        self._tools[name] = tool

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

    def _generate_parameters_schema(self, func: Callable) -> Dict[str, Any]:
        """
        Generate a JSON Schema-compliant schema for the function's parameters.

        Args:
            func (Callable): The function to generate the schema for.

        Returns:
            Dict[str, Any]: The JSON Schema for the function's parameters.
        """
        signature = inspect.signature(func)
        properties = {}
        required = []

        for name, param in signature.parameters.items():
            if name == "self":
                continue  # Skip 'self' for methods

            # Map Python types to JSON Schema types
            param_type = (
                self._map_python_type_to_json_schema(param.annotation)
                if param.annotation != inspect.Parameter.empty
                else "string"
            )

            # Add the parameter to the properties
            properties[name] = {
                "type": param_type,
                "description": f"The {name} parameter.",
            }

            # Check if the parameter is required
            if param.default == inspect.Parameter.empty:
                required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,  # Enforce strict parameter validation
        }

    def _map_python_type_to_json_schema(self, python_type: Any) -> str:
        """
        Map Python types to JSON Schema types.

        Args:
            python_type (Any): The Python type to map.

        Returns:
            str: The corresponding JSON Schema type.
        """
        type_mapping = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
        }

        # Handle cases where the type is a class (e.g., `int`, `str`)
        if hasattr(python_type, "__name__"):
            return type_mapping.get(python_type.__name__, "string")

        # Default to "string" if the type is not recognized
        return "string"

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
                },
            }
            for tool in self._tools.values()
        ]

    def get_callable(self, function_name: str) -> Callable:
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
        Execute tool calls and return results. Uses parallel execution for multiple tool calls
        and sequential execution for less than 3 tool calls to avoid thread pool overhead.

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
                tool = self.get_callable(function_name)
                if tool:
                    function_response = tool(**function_args)
                    tool_result = f"{function_name} -> {function_response}"
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

    def __getitem__(self, key: str) -> Callable:
        """
        Enable key-value access to retrieve callables.

        Args:
            key (str): The name of the function.

        Returns:
            Callable: The function to call, or None if not found.
        """
        return self.get_callable(key)
