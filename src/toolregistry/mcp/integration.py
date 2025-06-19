import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from fastmcp.client import Client, ClientTransport  # type: ignore
from fastmcp.server import FastMCP as FastMCPServer  # type: ignore
from loguru import logger
from mcp.server.fastmcp import FastMCP as FastMCP1Server  # type: ignore
from mcp.types import (
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    Implementation,
    InitializeResult,
    TextContent,
    TextResourceContents,
)
from mcp.types import Tool as ToolSpec
from pydantic import AnyUrl

from ..tool import Tool
from ..tool_registry import ToolRegistry
from ..tool_wrapper import BaseToolWrapper
from ..utils import normalize_tool_name
from .utils import get_initialize_result, infer_transport_overriden


class MCPToolWrapper(BaseToolWrapper):
    """Wrapper class providing both async and sync versions of MCP tool calls.

    Attributes:
        transport (ClientTransport): fastmcp.client.ClientTransport instance for communication.
        name (str): Name of the tool/operation.
        params (Optional[List[str]]): List of parameter names.
    """

    def __init__(
        self,
        transport: ClientTransport,
        name: str,
        params: Optional[List[str]],
    ) -> None:
        """Initialize MCP tool wrapper.

        Args:
            transport (ClientTransport): fastmcp.client.ClientTransport instance for communication.
            name (str): Name of the tool/operation.
            params (Optional[List[str]]): List of parameter names.
        """
        super().__init__(name=name, params=params)
        self.transport = transport

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
            if not self.transport or not self.name:
                raise ValueError("Client and name must be set before calling")

            async with Client(self.transport) as client:
                validated_params = {}
                kwargs = self._process_args(*args, **kwargs)
                for param_name in self.params:
                    if param_name in kwargs:
                        validated_params[param_name] = kwargs[param_name]

                result = await client.call_tool_mcp(self.name, validated_params)
                return self._post_process_result(result)

        except Exception as e:
            # record full exception stack
            import traceback

            logger.error(
                f"Original Exception happens at {self.name}:\n{traceback.format_exc()}"
            )
            raise  # throw to keep the original behavior

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
        tool_spec: ToolSpec,
        transport: ClientTransport,
        namespace: Optional[str] = None,
    ) -> "MCPTool":
        """Create an MCPTool instance from a JSON representation.

        Args:
            tool_spec (ToolSpec): The JSON representation of the tool.
            transport (ClientTransport): fastmcp.client.ClientTransport instance for communication.
            namespace (Optional[str]): An optional namespace to prefix the tool name.
                If provided, the tool name will be formatted as "{namespace}.{name}".

        Returns:
            MCPTool: A new instance of MCPTool configured with the provided parameters.
        """
        name = tool_spec.name
        description = tool_spec.description or ""
        input_schema = tool_spec.inputSchema

        wrapper = MCPToolWrapper(
            transport=transport,
            name=name,
            params=(
                list(input_schema.get("properties", {}).keys()) if input_schema else []
            ),
        )

        tool = cls(
            name=normalize_tool_name(name),
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
        transport: ClientTransport
        | FastMCPServer
        | FastMCP1Server
        | AnyUrl
        | Path
        | dict[str, Any]
        | str,
        with_namespace: Union[bool, str] = False,
    ) -> None:
        """Async implementation to register all tools from an MCP server.

        Args:
            transport (ClientTransport | FastMCPServer | FastMCP1Server | AnyUrl | Path | dict[str, Any] | str): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Existing ClientTransport instance
                - FastMCPServer | FastMCP1Server instance
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            RuntimeError: If connection to server fails.
        """
        transport = (
            transport
            if isinstance(transport, ClientTransport)
            else infer_transport_overriden(transport)
        )

        async with Client(transport) as client:
            init_result: InitializeResult
            if hasattr(client, "initialize_result"):  # since fastmcp 2.3.5
                init_result = client.initialize_result
            else:
                init_result = await get_initialize_result(transport)

            server_info: Optional[Implementation] = getattr(
                init_result, "serverInfo", None
            )

            if isinstance(with_namespace, str):
                namespace = with_namespace
            elif with_namespace:  # with_namespace is True
                namespace = server_info.name if server_info else "MCP sse service"
            else:
                namespace = None

            # Get available tools from server
            tools_response: List[ToolSpec] = await client.list_tools()
            # print(f"Found {len(tools_response)} tools on server")

            # Register each tool with a wrapper function
            for tool_spec in tools_response:
                mcp_sse_tool = MCPTool.from_tool_json(
                    tool_spec=tool_spec,
                    transport=transport,
                    namespace=namespace,
                )

                # Register the tool wrapper function
                self.registry.register(mcp_sse_tool, namespace=namespace)
                # print(f"Registered tool: {tool.name}")

    def register_mcp_tools(
        self,
        transport: ClientTransport
        | FastMCPServer
        | FastMCP1Server
        | AnyUrl
        | Path
        | dict[str, Any]
        | str,
        with_namespace: Union[bool, str] = False,
    ) -> None:
        """Register all tools from an MCP server (synchronous entry point).

        Args:
            transport (ClientTransport | FastMCPServer | FastMCP1Server | AnyUrl | Path | dict[str, Any] | str):
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Existing ClientTransport instance
                - FastMCP instance
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
        """
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                self.register_mcp_tools_async(transport, with_namespace)  # type: ignore[arg-type]
            )
        finally:
            loop.close()
