import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from fastmcp.client import Client, ClientTransport
from fastmcp.client.transports import (
    FastMCPServer,
    infer_transport,
)
from mcp.types import (
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    Implementation,
    InitializeResult,
    TextContent,
    TextResourceContents,
)

from .tool import Tool
from .tool_registry import ToolRegistry
from .utils import normalize_tool_name


class MCPToolWrapper:
    """Wrapper class providing both async and sync versions of MCP tool calls.

    Attributes:
        url (str): URL of the MCP server.
        name (str): Name of the tool/operation.
        params (Optional[List[str]]): List of parameter names.
    """

    def __init__(
        self,
        transport: str | Path | ClientTransport | FastMCPServer,
        name: str,
        params: Optional[List[str]],
    ) -> None:
        """Initialize MCP tool wrapper.

        Args:
            transport (str | Path | ClientTransport | FastMCPServer): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Existing ClientTransport instance
                - FastMCPServer instance
            name (str): Name of the tool/operation.
            params (Optional[List[str]]): List of parameter names.
        """
        self.client = Client(
            transport
            if isinstance(transport, ClientTransport)
            else infer_transport(transport)
        )
        self.name: str = name
        self.params: Optional[List[str]] = params

    def _process_args(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Process positional and keyword arguments into validated kwargs.

        Args:
            args (Any): Positional arguments to process.
            kwargs (Any): Keyword arguments to process.

        Returns:
            Dict[str, Any]: Validated keyword arguments.

        Raises:
            ValueError: If tool parameters not initialized.
            TypeError: If arguments are invalid or duplicated.
        """
        if args:
            if not self.params:
                raise ValueError("Tool parameters not initialized")
            if len(args) > len(self.params):
                raise TypeError(
                    f"Expected at most {len(self.params)} positional arguments, got {len(args)}"
                )
            # Map positional args to their corresponding parameter names
            for i, arg in enumerate(args):
                param_name = self.params[i]
                if param_name in kwargs:
                    raise TypeError(
                        f"Parameter '{param_name}' passed both as positional and keyword argument"
                    )
                kwargs[param_name] = arg
        return kwargs

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronous implementation of MCP tool call.

        Args:
            args (Any): Positional arguments to pass to the tool.
            kwargs (Any): Keyword arguments to pass to the tool.

        Returns:
            Any: Result from tool execution.

        Raises:
            ValueError: If URL or name not set.
            Exception: If tool execution fails.
        """
        kwargs = self._process_args(*args, **kwargs)

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.call_async(**kwargs))
        finally:
            loop.close()

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Async implementation of MCP tool call.

        Args:
            args (Any): Positional arguments to pass to the tool.
            kwargs (Any): Keyword arguments to pass to the tool.

        Returns:
            Any: Result from tool execution.

        Raises:
            ValueError: If URL or name not set.
            Exception: If tool execution fails.
        """
        try:
            kwargs = self._process_args(*args, **kwargs)
            if not self.client or not self.name:
                raise ValueError("Client and name must be set before calling")

            async with self.client:
                tools = await self.client.list_tools()
                tool = next((t for t in tools if t.name == self.name), None)
                if not tool:
                    raise ValueError(f"Tool {self.name} not found on server")

                validated_params = {}
                for param_name, _ in tool.inputSchema.get("properties", {}).items():
                    if param_name in kwargs:
                        validated_params[param_name] = kwargs[param_name]

                result = await self.client.call_tool(
                    self.name, validated_params, _return_raw_result=True
                )
                return self._post_process_result(result)

        except Exception as e:
            # record full exception stack
            import traceback

            print(
                f"Original Exception happens at {self.name}:\n{traceback.format_exc()}"
            )
            raise  # throw to keep the original behavior

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Make the wrapper directly callable, automatically choosing sync/async version.

        Args:
            args (Any): Positional arguments to pass to the tool.
            kwargs (Any): Keyword arguments to pass to the tool.

        Returns:
            Any: Result from tool execution.

        Raises:
            ValueError: If URL or name not set.
            Exception: If tool execution fails.
        """
        try:
            # 尝试获取当前的 event loop
            asyncio.get_running_loop()
            # 如果成功，说明在异步环境中
            return self.call_async(*args, **kwargs)
        except RuntimeError:
            # 捕获异常，说明在同步环境中
            return self.call_sync(*args, **kwargs)

    def _post_process_result(self, result: Any) -> Any:
        """Post-process the result from an MCP tool call.

        Args:
            result (Any): Raw result from MCP tool call.

        Returns:
            Any: Processed result (single value or list).

        Raises:
            NotImplementedError: If content type is not supported.
        """
        if isinstance(result, list):
            contents = result
        else:
            if result.isError or not result.content:
                return result
            contents = result.content

        def process_text(content: TextContent) -> str:
            return content.text

        def process_image(content: ImageContent) -> dict:
            return {
                "type": "image",
                "data": content.data,
                "mimeType": content.mimeType,
            }

        def process_embedded(content: EmbeddedResource) -> Any:
            if isinstance(content.resource, TextResourceContents):
                return content.resource.text
            elif isinstance(content.resource, BlobResourceContents):
                return {
                    "type": "blob",
                    "data": content.resource.blob,
                    "mimeType": content.resource.mimeType,
                }
            return content

        handlers: Dict[Any, Callable] = {
            TextContent: process_text,
            ImageContent: process_image,
            EmbeddedResource: process_embedded,
        }

        processed = []
        for content in contents:
            content_type = type(content)
            handler = handlers.get(content_type)
            if handler is None:
                raise NotImplementedError(
                    f"No handler for content type: {content_type}"
                )
            processed.append(handler(content))

        return processed[0] if len(processed) == 1 else processed


class MCPTool(Tool):
    """Wrapper class for MCP tools that preserves original function metadata.

    Attributes:
        name (str): Name of the tool.
        description (str): Description of the tool.
        parameters (Dict[str, Any]): Parameter schema definition.
        callable (Callable[..., Any]): The wrapped callable function.
        is_async (bool): Whether the tool is async, defaults to False.
    """

    @classmethod
    def from_tool_json(
        cls,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        transport: str | Path | ClientTransport | FastMCPServer,
        namespace: Optional[str] = None,
    ) -> "MCPTool":
        """Create an MCPTool instance from a JSON representation.

        Args:
            name (str): The name of the tool.
            description (str): The description of the tool.
            input_schema (Dict[str, Any]): The input schema definition for the tool.
            transport (str | Path | ClientTransport | FastMCPServer): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Existing ClientTransport instance
                - FastMCPServer instance
            namespace (Optional[str]): An optional namespace to prefix the tool name.
                If provided, the tool name will be formatted as "{namespace}.{name}".

        Returns:
            MCPTool: A new instance of MCPTool configured with the provided parameters.
        """
        func_name = normalize_tool_name(name)

        wrapper = MCPToolWrapper(
            transport=transport,
            name=func_name,
            params=(
                list(input_schema.get("properties", {}).keys()) if input_schema else []
            ),
        )
        tool = cls(
            name=func_name,
            description=description,
            parameters=input_schema,
            callable=wrapper,
            is_async=False,
        )

        if namespace:
            tool.update_namespace(namespace)

        return tool


class MCPIntegration:
    """Handles integration with MCP server for tool registration.

    Attributes:
        registry (ToolRegistry): Tool registry instance.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def register_mcp_tools_async(
        self,
        transport: str | Path | ClientTransport | FastMCPServer,
        with_namespace: Union[bool, str] = False,
    ) -> None:
        """Async implementation to register all tools from an MCP server.

        Args:
            transport (str | Path | ClientTransport | FastMCPServer): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Existing ClientTransport instance
                - FastMCPServer instance
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            RuntimeError: If connection to server fails.
        """

        client = Client(
            transport
            if isinstance(transport, ClientTransport)
            else infer_transport(transport)
        )
        async with client:
            # print("Connected to server, initializing session...")
            result: InitializeResult = await client.list_tools()
            server_info: Optional[Implementation] = getattr(result, "serverInfo", None)

            if isinstance(with_namespace, str):
                namespace = with_namespace
            elif with_namespace:  # with_namespace is True
                namespace = server_info.name if server_info else "MCP sse service"
            else:
                namespace = None

            # Get available tools from server
            tools_response = await client.list_tools()
            # print(f"Found {len(tools_response)} tools on server")

            # Register each tool with a wrapper function
            for tool_spec in tools_response:
                mcp_sse_tool = MCPTool.from_tool_json(
                    name=tool_spec.name,
                    description=tool_spec.description or "",
                    input_schema=tool_spec.inputSchema,
                    transport=transport,
                    namespace=namespace,
                )

                # Register the tool wrapper function
                self.registry.register(mcp_sse_tool, namespace=namespace)
                # print(f"Registered tool: {tool.name}")

    def register_mcp_tools(
        self,
        transport: str | Path | ClientTransport | FastMCPServer,
        with_namespace: Union[bool, str] = False,
    ) -> None:
        """Register all tools from an MCP server (synchronous entry point).

        Args:
            transport (str | Path | ClientTransport | FastMCPServer): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Existing ClientTransport instance
                - FastMCPServer instance
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
        """
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                self.register_mcp_tools_async(transport, with_namespace)
            )
        finally:
            loop.close()
