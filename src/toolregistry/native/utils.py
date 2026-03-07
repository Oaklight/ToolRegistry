from typing import List, Optional, Type, Union


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


def get_all_static_methods(
    cls_or_instance: Union[Type, object],
    skip_list: Optional[List[str]] = None,
    include_list: Optional[List[str]] = None,
) -> List[str]:
    """Returns a list of all valid public static methods of a class or its instance.

    Args:
        cls_or_instance (Union[Type, object]): The class type or instance from which
            static methods will be retrieved.
        skip_list (Optional[List[str]]): A list of method names to explicitly skip.
        include_list (Optional[List[str]]): A list of method names to explicitly include.

    Returns:
        List[str]: A list of names of all valid public static methods in the class.

    Example:
        >>> class Example:
        ...     @staticmethod
        ...     def static_method_one():
        ...         pass
        ...
        ...     @staticmethod
        ...     def static_method_two():
        ...         pass
        ...
        >>> get_all_static_methods(Example, skip_list=["static_method_two"])
        ['static_method_one']
        >>> get_all_static_methods(Example, include_list=["static_method_two", "static_method_three"])
        ['static_method_two']
    """
    cls = (
        cls_or_instance
        if isinstance(cls_or_instance, type)
        else cls_or_instance.__class__
    )
    skip_list = skip_list or []
    include_list = include_list or []

    static_methods = []
    for name, attr in cls.__dict__.items():
        if isinstance(attr, staticmethod):
            # Check if the method is public (does not start with '_')
            if not name.startswith("_"):
                # Include the method only if it's in include_list, or if include_list is empty
                if (not include_list or name in include_list) and name not in skip_list:
                    static_methods.append(name)

    # Ensure all returned names are valid in the instance or type
    valid_methods = [name for name in static_methods if hasattr(cls_or_instance, name)]
    return valid_methods
