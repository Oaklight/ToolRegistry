from typing import Optional, Type, Union


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
