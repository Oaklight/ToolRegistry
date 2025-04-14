"""Integration for registering class static methods as tools.

This module provides functionality to scan a Python class and register all its
static methods (@staticmethod) as tools in a ToolRegistry.

Example:
    >>> from toolregistry import ToolRegistry
    >>> from toolregistry.hub import Calculator
    >>> registry = ToolRegistry()
    >>> registry.register_static_tools(Calculator)
    >>> registry.get_available_tools()
    ['Calculator.add', 'Calculator.subtract', ...]
"""

import inspect
from typing import Type, Union

from .tool_registry import ToolRegistry


class StaticMethodIntegration:
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

    def register_static_methods(
        self, cls: Type, with_namespace: Union[bool, str] = False
    ) -> None:
        """Register all static methods from a class as tools.

        Args:
            cls (Type): The class to scan for static methods.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the class name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
        """
        if isinstance(with_namespace, str):
            namespace = with_namespace
        elif with_namespace:  # with_namespace is True
            namespace = cls.__name__
        else:
            namespace = None

        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if not inspect.isfunction(method):  # skip if not static method
                continue
            self.registry.register(method, namespace=namespace)

    async def register_static_methods_async(
        self, cls: Type, with_namespace: Union[bool, str] = False
    ) -> None:
        """Async implementation to register all static methods from a class as tools.

        Args:
            cls (Type): The class to scan for static methods.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
        """
        # Currently same as sync version since registration is not IO-bound
        self.register_static_methods(cls, with_namespace)
