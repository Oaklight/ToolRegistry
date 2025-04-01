import json
from typing import Any, Callable, Dict, List, Optional, Union

from .tool import Tool


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

    def get_available_tools(self) -> List[str]:
        """
        List all registered tools.
        Returns:
            List[str]: A list of tool names.
        """

        return list(self._tools.keys())

    def get_tools_json(self, tool_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get the JSON representation of all registered tools, following JSON Schema.

        Returns:
            List[Dict[str, Any]]: A list of tools in JSON format, compliant with JSON Schema.
        """
        if tool_name:
            target_tool = self.get_tool(tool_name)
            tools = [target_tool] if target_tool else []
        else:
            tools = list(self._tools.values())

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
            for tool in tools
        ]

    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        Get a tool by its name.

        Args:
            tool_name (str): The name of the tool.

        Returns:
           Tool: The tool, or None if not found.
        """
        tool = self._tools.get(tool_name)
        return tool

    def get_callable(self, tool_name: str) -> Optional[Callable[..., Any]]:
        """
        Get a callable function by its name.

        Args:
            tool_name (str): The name of the function.

        Returns:
            Callable: The function to call, or None if not found.
        """
        tool = self.get_tool(tool_name)
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
                tool = self.get_tool(function_name)
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
                    "content": f"{tool_call.function.name} --> {tool_responses[tool_call.id]}",
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
