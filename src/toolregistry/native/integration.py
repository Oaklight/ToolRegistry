"""Integration for registering class-based tools as tools.

This module provides functionality to scan a Python class and register its
methods as tools. If the class only contains static methods, they are registered
directly. If there are instance methods or other non-static attributes, the class
will be instantiated and its callable public methods will be registered.

Example:
    ```python
    from toolregistry import ToolRegistry
    registry = ToolRegistry()
    registry.register_from_class(MyClass)
    registry.list_tools()  # ['MyClass.method1', 'MyClass.method2', ...]
    ```
"""

import asyncio
import inspect

from ..tool_registry import ToolRegistry
from .utils import _determine_namespace, _is_all_static_methods


class ClassToolIntegration:
    def __init__(self, registry: ToolRegistry, traverse_mro: bool = True) -> None:
        """Initialize with a ToolRegistry instance.

        Args:
            registry (ToolRegistry): The tool registry to register methods with.
            traverse_mro (bool): Whether to traverse the MRO (Method Resolution Order)
                to include inherited methods. When True (default), methods from
                parent classes are also included (excluding ``object``), with
                subclass methods taking priority over parent class methods.
                When False, only methods defined directly on the class are
                registered.
        """
        self.registry = registry
        self.traverse_mro = traverse_mro

    def register_class_methods(
        self,
        cls_or_instance: type | object,
        namespace: bool | str = False,
    ) -> None:
        """Register all methods from a class or instance as tools.

        If a class is provided:
            - If all public methods are static, they are registered directly.
            - Otherwise, the class is instantiated and its public callable methods are registered.
        If an instance is provided:
            - Its public callable methods are registered directly.

        Args:
            cls_or_instance (Union[Type, object]): The class or instance to scan for methods.
            namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If False, no namespace is used.
                - If True, the namespace is derived from the class name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
        """
        resolved_ns = _determine_namespace(cls_or_instance, namespace)

        if isinstance(cls_or_instance, type):
            if _is_all_static_methods(cls_or_instance):
                self._register_static_methods(cls_or_instance, resolved_ns)
            else:
                try:
                    instance = cls_or_instance()
                except TypeError as e:
                    raise TypeError(
                        f"Try to register methods from class {cls_or_instance.__name__}. "
                        "Found mixed static and instance methods. "
                        "Attempted to instantiate the class, but failed without arguments. "
                        "Please provide an instance of the class."
                    ) from e
                self._register_instance_methods(instance, resolved_ns)
        else:
            self._register_instance_methods(cls_or_instance, resolved_ns)

    async def register_class_methods_async(
        self,
        cls_or_instance: type | object,
        namespace: bool | str = False,
    ) -> None:
        """Async implementation to register tools from a class.

        Currently, this is implemented synchronously.

        Args:
            cls_or_instance (Union[Type, object]): The class or instance to scan for methods.
            namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If False, no namespace is used.
                - If True, the namespace is derived from the class name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, self.register_class_methods, cls_or_instance, namespace
        )

    def _collect_static_methods_from_mro(self, cls: type) -> dict:
        """Collect static methods by traversing the MRO, with subclass priority.

        Iterates through ``inspect.getmro(cls)`` in reverse order (from the
        most base class to the most derived) so that subclass methods
        naturally override parent class methods.  Methods from ``object``
        are excluded.

        Args:
            cls (Type): The class whose MRO will be traversed.

        Returns:
            dict: A mapping of method name to ``staticmethod`` descriptor,
                with subclass versions taking priority.
        """
        collected: dict = {}
        for klass in reversed(inspect.getmro(cls)):
            if klass is object:
                continue
            for name, member in klass.__dict__.items():
                if not name.startswith("_") and isinstance(member, staticmethod):
                    collected[name] = member
        return collected

    def _register_static_methods(self, cls: type, namespace: str | None) -> None:
        """Register all static methods of a class into the provided registry.

        When ``self.traverse_mro`` is True (default), methods inherited from
        parent classes (excluding ``object``) are also included, with
        subclass methods taking priority over parent class methods.
        When False, only methods defined directly on *cls* are registered.

        Args:
            cls (Type): The class whose static methods will be registered.
            namespace (Optional[str]): The namespace under which the static
                methods will be registered.
        """
        if self.traverse_mro:
            methods = self._collect_static_methods_from_mro(cls)
        else:
            methods = {
                name: member
                for name, member in cls.__dict__.items()
                if not name.startswith("_") and isinstance(member, staticmethod)
            }

        for name, member in methods.items():
            self.registry.register(
                member.__func__, namespace=namespace, method_name=name
            )

    def _collect_instance_methods_from_mro(self, instance: object) -> dict:
        """Collect instance methods by traversing the MRO, with subclass priority.

        Iterates through ``inspect.getmro(type(instance))`` in reverse order
        so that subclass methods naturally override parent class methods.
        Methods from ``object`` are excluded, as are private methods and
        classmethods.

        Args:
            instance (object): The instance whose class MRO will be traversed.

        Returns:
            dict: A mapping of method name to the bound method, with subclass
                versions taking priority.
        """
        collected: dict = {}
        for klass in reversed(inspect.getmro(type(instance))):
            if klass is object:
                continue
            for name, member in klass.__dict__.items():
                if name.startswith("_"):
                    continue
                if isinstance(member, classmethod):
                    continue
                # Check if it's callable on the instance
                attr = getattr(instance, name, None)
                if attr is not None and callable(attr):
                    collected[name] = attr
        return collected

    def _register_instance_methods(
        self, instance: object, namespace: str | None
    ) -> None:
        """Register all instance methods (excluding private and classmethods) of an object.

        When ``self.traverse_mro`` is True (default), methods inherited from
        parent classes (excluding ``object``) are also included, with
        subclass methods taking priority.  When False, only methods visible
        via ``dir(instance)`` that are defined on the instance's own class
        are registered.

        Args:
            instance (object): The object whose instance methods will be
                registered.
            namespace (Optional[str]): The namespace under which the instance
                methods will be registered.
        """
        if self.traverse_mro:
            methods = self._collect_instance_methods_from_mro(instance)
            for name, attr in methods.items():
                self.registry.register(attr, namespace=namespace, method_name=name)
        else:
            for name in dir(instance):
                if name.startswith("_"):
                    continue
                # Exclude classmethods
                member = type(instance).__dict__.get(name, None)
                if isinstance(member, classmethod):
                    continue
                attr = getattr(instance, name)
                if callable(attr):
                    self.registry.register(attr, namespace=namespace, method_name=name)
