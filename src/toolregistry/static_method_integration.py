"""Integration for registering class-based tools as tools.

This module provides functionality to scan a Python class and register its
methods as tools. If the class only contains static methods, they are registered
directly. If there are instance methods or other non-static attributes, the class
will be instantiated and its callable public methods will be registered.

Example:
    >>> from toolregistry import ToolRegistry
    >>> registry = ToolRegistry()
    >>> registry.register_class_tool(MyClass)
    >>> registry.get_available_tools()
    ['MyClass.method1', 'MyClass.method2', ...]
"""

import inspect
from typing import Type, Union

from .tool_registry import ToolRegistry


class ClassToolIntegration:
    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize with a ToolRegistry instance.

        Args:
            registry (ToolRegistry): The tool registry to register methods with.
        """
        self.registry = registry

    def register_class_methods(
        self, cls: Type, with_namespace: Union[bool, str] = False
    ) -> None:
        """Register all methods from a class as tools.

        If all public methods are static, they are registered directly.
        Otherwise, the class is instantiated and its public callable methods are registered.

        Args:
            cls (Type): The class to scan for methods.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If False, no namespace is used.
                - If True, the namespace is derived from the class name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
        """
        # Determine if all public methods defined in the class are static methods.
        all_static = True
        for name, member in cls.__dict__.items():
            if not name.startswith("_"):
                if not isinstance(member, staticmethod):
                    all_static = False
                    break

        # Determine namespace to use.
        if isinstance(with_namespace, str):
            namespace = with_namespace
        elif with_namespace:
            namespace = cls.__name__
        else:
            namespace = None

        if all_static:
            # Register static methods directly.
            for name, member in cls.__dict__.items():
                if not name.startswith("_") and isinstance(member, staticmethod):
                    # member.__func__ provides the underlying function.
                    self.registry.register(member.__func__, namespace=namespace)
        else:
            # Instantiate the class.
            instance = cls()
            # Register all callable public attributes.
            for name in dir(instance):
                if name.startswith("_"):
                    continue
                attr = getattr(instance, name)
                if callable(attr):
                    self.registry.register(attr, namespace=namespace)

    async def register_class_methods_async(
        self, cls: Type, with_namespace: Union[bool, str] = False
    ) -> None:
        """Async implementation to register tools from a class.

        Currently, this is implemented synchronously.

        Args:
            cls (Type): The class to scan for methods.
            with_namespace (Union[bool, str]): Namespace option.
        """
        self.register_class_methods(cls, with_namespace)
