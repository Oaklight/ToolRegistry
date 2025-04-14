import inspect
from typing import Any, Callable, Dict, Optional, Tuple, Type, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic.fields import FieldInfo


class InvalidSignature(Exception):
    """Exception raised when a function signature cannot be processed for FastMCP.

    Attributes:
        message (str): Explanation of the error.
    """


class ArgModelBase(BaseModel):
    """Base model for function argument validation with Pydantic.

    Features:
        - Supports arbitrary types in fields
        - Provides method to dump fields one level deep
        - Configures Pydantic model behavior
    """

    def model_dump_one_level(self) -> Dict[str, Any]:
        """Dump model fields one level deep, keeping sub-models as-is.

        Returns:
            Dict[str, Any]: Dictionary of field names to values.
        """
        return {field: getattr(self, field) for field in self.__pydantic_fields__}

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


def _get_typed_annotation(annotation: Any, globalns: Dict[str, Any]) -> Any:
    """Evaluate type annotation, handling forward references.

    Uses Python's public get_type_hints function rather than relying on a pydantic internal function.

    Args:
        annotation (Any): The annotation to evaluate (can be string forward reference).
        globalns (Dict[str, Any]): The global namespace to use for evaluating the annotation.

    Returns:
        Any: The evaluated annotation.

    Raises:
        InvalidSignature: If unable to evaluate type annotation.
    """

    if isinstance(annotation, str):
        # Create a dummy function with a parameter annotated by the string.
        def dummy(a: Any):
            pass

        # Manually set the annotation on the dummy function.
        dummy.__annotations__ = {"a": annotation}
        try:
            hints = get_type_hints(dummy, globalns)
            return hints["a"]
        except Exception as e:
            raise InvalidSignature(
                f"Unable to evaluate type annotation {annotation}"
            ) from e

    return annotation


def _create_field(
    param: inspect.Parameter, annotation_type: Any
) -> Tuple[Any, FieldInfo]:
    """Create a Pydantic field for a function parameter.

    Handles both annotated and unannotated parameters, with and without defaults.

    Args:
        param (inspect.Parameter): The parameter to create a field for.
        annotation_type (Any): The type annotation for the parameter.

    Returns:
        Tuple[Any, FieldInfo]: A tuple of (annotated_type, field_info).
    """
    default = param.default if param.default is not inspect.Parameter.empty else None
    if param.default is inspect.Parameter.empty:
        field_info = (
            Field(title=param.name)
            if param.annotation is inspect.Parameter.empty
            else Field()
        )
        return (annotation_type, field_info)
    else:
        field_info = (
            Field(default=default, title=param.name)
            if param.annotation is inspect.Parameter.empty
            else Field(default=default)
        )
        return (Optional[annotation_type], field_info)


def _generate_parameters_model(func: Callable) -> Optional[Type[ArgModelBase]]:
    """Generate a Pydantic model from a function's parameters.

    Creates a JSON Schema-compliant model that can validate the function's parameters.

    Args:
        func (Callable): The function to generate the parameter model for.

    Returns:
        Optional[Type[ArgModelBase]]: Pydantic model class for the parameters, or None on error.

    Raises:
        InvalidSignature: If unable to process function signature.
    """
    try:
        signature = inspect.signature(func)
        globalns = getattr(func, "__globals__", {})
        dynamic_model_creation_dict: Dict[str, Any] = {}

        for param in signature.parameters.values():
            if param.name == "self":
                continue

            annotation = _get_typed_annotation(param.annotation, globalns)
            if param.annotation is inspect.Parameter.empty:
                dynamic_model_creation_dict[param.name] = _create_field(param, Any)
            elif param.annotation is None:
                dynamic_model_creation_dict[param.name] = _create_field(param, None)
            else:
                dynamic_model_creation_dict[param.name] = _create_field(
                    param, annotation
                )

        return create_model(
            f"{func.__name__}Parameters",
            **dynamic_model_creation_dict,
            __base__=ArgModelBase,
        )
    except Exception as e:
        return None
