"""Namespace mixin for ToolRegistry."""

from __future__ import annotations

from typing import Any
from collections.abc import Callable

from ..tool import Tool


class NamespaceMixin:
    """Mixin providing namespace management, tool lookup, merge, and spinoff."""

    name: str

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tools: dict[str, Tool] = {}
        self._sub_registries: set[str] = set()

    def _update_sub_registries(self) -> None:
        """Update the internal set of sub-registries based on the registered tools.

        This method identifies sub-registry prefixes by examining the ``namespace``
        field of each tool first.  If a tool does not have a ``namespace`` set, it
        falls back to parsing the tool name for a dot-separated prefix.

        Side Effects:
            Modifies the `_sub_registries` attribute with the latest prefixes.

        Returns:
            None
        """
        prefixes: set[str] = set()
        for tool in self._tools.values():
            if tool.namespace:
                prefixes.add(tool.namespace)
            elif "." in tool.name:
                prefixes.add(tool.name.split(".", 1)[0])
        self._sub_registries = prefixes

    def _prefix_tools_namespace(self, force: bool = False) -> None:
        """Add the registry name as a prefix to the names of tools in the registry.

        This method updates the names of tools in the `_tools` dictionary by prefixing
        them with the registry's name if they don't already have a prefix. Tools that
        already have a prefix retain their existing name.

        Args:
            force (bool): If True, forces the namespace update for all tools, even if they already have a prefix.
                If False, retains existing prefixes for tools that already have one.

        Side Effects:
            Updates the `_tools` dictionary with potentially modified tool names.

        Example:
            If the registry name is "MainRegistry":
            - A tool with the name "tool_a" will be updated to "main_registry.tool_a".
            - A tool with the name "other_registry.tool_b" will remain unchanged if force=False.
            - A tool with the name "other_registry.tool_b" will be updated to "main_registry.tool_b" if force=True.

        Raises:
            None
        """
        new_tools: dict[str, Tool] = {}
        for tool in self._tools.values():
            tool.update_namespace(self.name, force=force)
            new_tools[tool.name] = tool
        self._tools = new_tools

    def merge(
        self,
        other: NamespaceMixin,
        keep_existing: bool = False,
        force_namespace: bool = False,
    ):
        """Merge tools from another ToolRegistry into this one.

        This method directly updates the current registry with tools from another
        registry, avoiding the need to create a new ToolRegistry object.

        Args:
            other (ToolRegistry): The ToolRegistry to merge from.
            keep_existing (bool): If True, preserves existing tools on name conflicts.
            force_namespace (bool): If True, forces updating tool namespaces by prefixing them with the registry name; if False, retains existing namespaces.

        Raises:
            TypeError: If other is not a ToolRegistry instance.
        """
        from ..tool_registry import ToolRegistry

        if not isinstance(other, ToolRegistry):
            raise TypeError("Can only merge with another ToolRegistry instance.")

        # Prefix tools in both registries
        self._prefix_tools_namespace()
        other._prefix_tools_namespace()

        # Merge tools based on the `keep_existing` flag
        if keep_existing:
            for name, tool in other._tools.items():
                if name not in self._tools:
                    self._tools[name] = tool
        else:
            self._tools.update(other._tools)

        if force_namespace:
            # update namespace if required after merge done
            self._prefix_tools_namespace(force=force_namespace)

        # Update sub-registries based on merged tools
        self._update_sub_registries()

    def reduce_namespace(self) -> None:
        """Remove the namespace from tools in the registry if there is only one sub-registry.

        This method checks if there is only one sub-registry remaining in the registry.
        If so, it removes the namespace prefix from all tools and clears the sub-registries.

        Side Effects:
            - Updates the `_tools` dictionary to remove namespace prefixes.
            - Clears the `_sub_registries` set if namespace flattening occurs.

        Example:
            If the registry contains tools with names like "calculator.add" and "calculator.subtract",
            and "calculator" is the only sub-registry, this method will rename the tools to "add" and "subtract".
        """
        if len(self._sub_registries) == 1:
            remaining_prefix = next(iter(self._sub_registries))
            self._tools = {
                name[len(remaining_prefix) + 1 :]: tool
                for name, tool in self._tools.items()
            }
            self._sub_registries.clear()

    def spinoff(self, prefix: str, retain_namespace: bool = False) -> NamespaceMixin:
        """Spin off tools with the specified prefix into a new registry.

        This method creates a new ToolRegistry, transferring tools that belong
        to the specified prefix to it, and removing them from the current registry.

        Args:
            prefix (str): Prefix to identify tools to spin off.
            retain_namespace (bool): If True, retains the namespace of tools in the current registry.
                If False, removes the namespace from tools after spinning off.

        Returns:
            ToolRegistry: A new registry containing the spun-off tools.

        Raises:
            ValueError: If no tools with the specified prefix are found.

        Notes:
            When `retain_namespace` is False, the `reduce_namespace` method is called
            to remove the namespace from tools in the current registry.
        """
        from ..tool_registry import ToolRegistry

        # Filter tools with the specified prefix
        spun_off_tools = {
            name: tool
            for name, tool in self._tools.items()
            if name.startswith(f"{prefix}.")
        }

        if not spun_off_tools:
            raise ValueError(f"No tools with prefix '{prefix}' found in the registry.")

        # Create a new registry for the spun-off tools
        new_registry = ToolRegistry(name=prefix)
        new_registry._sub_registries.add(prefix)
        new_registry._tools = spun_off_tools  # Initialize with spun-off tools
        if not retain_namespace:
            new_registry.reduce_namespace()  # Optimize namespace removal using reduce_namespace

        # Remove the spun-off tools from the current registry
        self._tools = {
            name: tool
            for name, tool in self._tools.items()
            if not name.startswith(f"{prefix}.")
        }

        # Remove the prefix from sub-registries if it exists
        self._sub_registries.discard(prefix)

        # Optionally discard namespace if retain_namespace is False
        if not retain_namespace:
            self.reduce_namespace()

        return new_registry

    def get_tool(self, tool_name: str) -> Tool | None:
        """Get a tool by its name.

        Args:
            tool_name (str): Name of the tool to retrieve.

        Returns:
            Optional[Tool]: The tool, or None if not found.
        """
        tool = self._tools.get(tool_name)
        return tool

    def get_callable(self, tool_name: str) -> Callable[..., Any] | None:
        """Get a callable function by its name.

        Args:
            tool_name (str): Name of the function to retrieve.

        Returns:
            Optional[Callable[..., Any]]: The function to call, or None if not found.
        """
        tool = self.get_tool(tool_name)
        return tool.callable if tool else None
