"""Integration for registering class static methods as tools.

This module provides functionality to scan a Python class and register all its
static methods (@staticmethod) as tools in a ToolRegistry.

Example:
    >>> from toolregistry import ToolRegistry
    >>> from toolregistry.hub import Calculator
    >>> registry = ToolRegistry()
    >>> registry.register_hub_tools(Calculator)
    >>> registry.get_available_tools()
    ['Calculator.add', 'Calculator.subtract', ...]
"""

import inspect
from typing import Type

from .tool_registry import ToolRegistry


class HubIntegration:
    """Handles registration of class static methods as tools.

    Attributes:
        registry (ToolRegistry): The tool registry to register methods with.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize with a ToolRegistry instance.

        Args:
            registry (ToolRegistry): The tool registry to register methods with.
        """
        self.registry = registry

    def register_hub_tools(self, cls: Type, with_namespace: bool = False) -> None:
        """Register all static methods from a class as tools.

        Args:
            cls (Type): The class to scan for static methods.
        """
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if not inspect.isfunction(method):  # skip if not static method
                continue
            if with_namespace:
                self.registry.register(method, name=name, namespace=cls.__name__)
            else:
                self.registry.register(method, name=name)

    async def register_hub_tools_async(
        self, cls: Type, with_namespace: bool = False
    ) -> None:
        """Async implementation to register all static methods from a class as tools.

        Args:
            cls (Type): The class to scan for static methods.
        """
        # Currently same as sync version since registration is not IO-bound
        self.register_hub_tools(cls)
