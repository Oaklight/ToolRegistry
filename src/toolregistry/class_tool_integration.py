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

import asyncio
from typing import Optional, Type, Union

from .tool_registry import ToolRegistry


def _is_all_static_methods(cls: Type) -> bool:
    """
    Determines if all the methods of a given class are static methods.

    Args:
        cls (Type): The class to check.

    Returns:
        bool: True if all non-private methods of the class are static methods; otherwise, False.
    """
    for name, member in cls.__dict__.items():
        if not name.startswith("_") and not isinstance(member, staticmethod):
            return False
    return True


def _determine_namespace(
    cls_or_inst: Union[Type, object], with_ns: Union[str, bool]
) -> Optional[str]:
    """
    Determines the namespace to use based on the class or instance and the `with_ns` parameter.

    Args:
        cls_or_inst (Union[Type, object]): The class or instance to derive the namespace from.
        with_ns (Union[str, bool]): Either a string representing the namespace,
                                    True for using the class or instance name,
                                    or False for no namespace.

    Returns:
        Optional[str]: The derived namespace, or None if `with_ns` is False.
    """
    if isinstance(with_ns, str):
        return with_ns
    elif with_ns:
        if isinstance(cls_or_inst, type):
            return cls_or_inst.__name__
        else:
            return type(cls_or_inst).__name__
    else:
        return None


def _register_static_methods(
    cls: Type, registry: ToolRegistry, namespace: Optional[str]
) -> None:
    """
    Registers all static methods of a class into the provided registry.

    Args:
        cls (Type): The class whose static methods will be registered.
        registry (ToolRegistry): The registry object to register the methods into.
                             It is expected to have a `register` method.
        namespace (Optional[str]): The namespace under which the static methods will be registered.
    """
    for name, member in cls.__dict__.items():
        if not name.startswith("_") and isinstance(member, staticmethod):
            registry.register(member.__func__, namespace=namespace)


def _register_instance_methods(
    instance: object, registry: ToolRegistry, namespace: Optional[str]
) -> None:
    """
    Registers all instance methods (excluding private methods and classmethods) of an object into the registry.

    Args:
        instance (object): The object whose instance methods will be registered.
        registry (ToolRegistry): The registry object to register the methods into.
                             It is expected to have a `register` method.
        namespace (Optional[str]): The namespace under which the instance methods will be registered.
    """
    for name in dir(instance):
        if name.startswith("_"):
            continue
        # Exclude classmethods
        member = type(instance).__dict__.get(name, None)
        if isinstance(member, classmethod):
            continue
        attr = getattr(instance, name)
        if callable(attr):
            registry.register(attr, namespace=namespace)


class ClassToolIntegration:
    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize with a ToolRegistry instance.

        Args:
            registry (ToolRegistry): The tool registry to register methods with.
        """
        self.registry = registry

    def register_class_methods(
        self,
        cls_or_instance: Union[Type, object],
        with_namespace: Union[bool, str] = False,
    ) -> None:
        """Register all methods from a class or instance as tools.

        If a class is provided:
            - If all public methods are static, they are registered directly.
            - Otherwise, the class is instantiated and its public callable methods are registered.
        If an instance is provided:
            - Its public callable methods are registered directly.

        Args:
            cls_or_instance (Union[Type, object]): The class or instance to scan for methods.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If False, no namespace is used.
                - If True, the namespace is derived from the class name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
        """
        namespace = _determine_namespace(cls_or_instance, with_namespace)

        if isinstance(cls_or_instance, type):
            if _is_all_static_methods(cls_or_instance):
                _register_static_methods(cls_or_instance, self.registry, namespace)
            else:
                try:
                    instance = cls_or_instance()
                except TypeError as e:
                    raise TypeError(
                        f"Cannot instantiate class {cls_or_instance.__name__} without arguments. "
                        "Please provide an instance of the class."
                    ) from e
                _register_instance_methods(instance, self.registry, namespace)
        else:
            _register_instance_methods(cls_or_instance, self.registry, namespace)

    async def register_class_methods_async(
        self,
        cls_or_instance: Union[Type, object],
        with_namespace: Union[bool, str] = False,
    ) -> None:
        """Async implementation to register tools from a class.

        Currently, this is implemented synchronously.

        Args:
            cls_or_instance (Union[Type, object]): The class or instance to scan for methods.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If False, no namespace is used.
                - If True, the namespace is derived from the class name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, self.register_class_methods, cls_or_instance, with_namespace
        )