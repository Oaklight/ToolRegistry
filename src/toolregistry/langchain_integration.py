import asyncio
from typing import Any, List, Optional, Union

from langchain_core.tools import BaseTool as LCBaseTool  # type: ignore
from loguru import logger

from .tool import Tool
from .tool_registry import ToolRegistry
from .tool_wrapper import BaseToolWrapper
from .utils import normalize_tool_name


class LangChainToolWrapper(BaseToolWrapper):
    """Wrapper class providing both async and sync versions of LangChain tool calls.

    Attributes:
        tool (LCBaseTool): The LangChain tool instance.
        name (str): Name of the tool.
        description (str): Description of the tool.
        params (List[str]): List of parameter names.
    """

    def __init__(self, tool: LCBaseTool) -> None:
        """Initialize LangChain tool wrapper.

        Args:
            tool (LCBaseTool): The LangChain tool instance.
        """
        super().__init__(
            name=normalize_tool_name(tool.name),
            params=list(tool.args.keys()),
        )
        self.tool = tool

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronous implementation of LangChain tool call.

        Args:
            args (Any): Positional arguments to pass to the tool.
            kwargs (Any): Keyword arguments to pass to the tool.

        Returns:
            Any: Result from tool execution.

        Raises:
            ToolException: If tool execution fails.
        """
        try:
            return self.tool._run(*args, **kwargs)
        except Exception as e:
            import traceback

            logger.error(
                f"Original Exception happens at {self.name}:\n{traceback.format_exc()}"
            )
            raise  # throw to keep the original behavior

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Async implementation of LangChain tool call.

        Args:
            args (Any): Positional arguments to pass to the tool.
            kwargs (Any): Keyword arguments to pass to the tool.

        Returns:
            Any: Result from tool execution.

        Raises:
            ToolException: If tool execution fails.
        """
        try:
            return await self.tool._arun(*args, **kwargs)
        except Exception as e:
            import traceback

            logger.error(
                f"Original Exception happens at {self.name}:\n{traceback.format_exc()}"
            )
            raise  # throw to keep the original behavior


class LangChainTool(Tool):
    """Wrapper class for LangChain tools that preserves original function metadata."""

    @classmethod
    def from_langchain_tool(
        cls,
        tool: LCBaseTool,
        namespace: Optional[str] = None,
    ) -> "LangChainTool":
        """Create a LangChainTool instance from a LangChain LCBaseTool.

        Args:
            tool (LCBaseTool): The LangChain tool instance.
            namespace (Optional[str]): An optional namespace to prefix the tool name.
                If provided, the tool name will be formatted as "{namespace}.{name}".

        Returns:
            LangChainTool: A new instance of LangChainTool.
        """
        wrapper = LangChainToolWrapper(tool)

        # We need to do a bit surgery here. Some tool's input docstring is not properly set.
        input_schema = tool.input_schema.model_json_schema()
        del input_schema["description"]  # del it for the sake of consistency

        tool_instance = cls(
            name=wrapper.name,
            description=wrapper.tool.description,
            parameters=input_schema,
            callable=wrapper,
            is_async=False,
        )

        if namespace:
            tool_instance.update_namespace(namespace)

        return tool_instance


class LangChainIntegration:
    """Handles integration with LangChain tools for registration.

    Attributes:
        registry (ToolRegistry): Tool registry instance.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def register_langchain_tools_async(
        self,
        tools: Union[LCBaseTool, List[LCBaseTool]],
        with_namespace: Union[bool, str] = False,
    ) -> None:
        """Async implementation to register LangChain tools using asyncio.

        Args:
            tools (Union[LCBaseTool, List[LCBaseTool]]): Single tool or list of tools to register.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the tool's metadata if available.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            ValueError: If tools argument is invalid.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, self.register_langchain_tools, tools, with_namespace
        )

    def register_langchain_tools(
        self,
        tools: Union[LCBaseTool, List[LCBaseTool]],
        with_namespace: Union[bool, str] = False,
    ) -> None:
        """Register LangChain tools (synchronous entry point).

        Args:
            tools (Union[LCBaseTool, List[LCBaseTool]]): Single tool or list of tools to register.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the tool's metadata if available.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
        """
        if not isinstance(tools, list):
            tools = [tools]

        for tool in tools:
            if not isinstance(tool, LCBaseTool):
                raise ValueError(
                    f"Expected `langchain_core.tools.BaseTool` instance, got {type(tool)}"
                )

            if isinstance(with_namespace, str):
                namespace = with_namespace
            elif with_namespace:  # with_namespace is True
                namespace = "langchain tool"
            else:
                namespace = None

            langchain_tool = LangChainTool.from_langchain_tool(
                tool=tool,
                namespace=namespace,
            )
            self.registry.register(langchain_tool, namespace=namespace)
