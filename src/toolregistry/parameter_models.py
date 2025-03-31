import inspect
from typing import Any, Dict, ForwardRef, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic._internal._typing_extra import eval_type_backport
from pydantic.fields import FieldInfo


class InvalidSignature(Exception):
    """Invalid signature for use with FastMCP."""


class ArgModelBase(BaseModel):
    """A model representing the arguments to a function.

    Features:
    - Supports arbitrary types in fields.
    - Provides a method to dump fields one level deep.
    """

    def model_dump_one_level(self) -> Dict[str, Any]:
        """Dump model fields one level deep, keeping sub-models as-is."""
        return {field: getattr(self, field) for field in self.__pydantic_fields__}

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


def _get_typed_annotation(annotation: Any, globalns: dict[str, Any]) -> Any:
    def try_eval_type(
        value: Any, globalns: dict[str, Any], localns: dict[str, Any]
    ) -> tuple[Any, bool]:
        try:
            return eval_type_backport(value, globalns, localns), True
        except NameError:
            return value, False

    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)
        annotation, status = try_eval_type(annotation, globalns, globalns)

        # This check and raise could perhaps be skipped, and we (FastMCP) just call
        # model_rebuild right before using it 🤷
        if status is False:
            raise InvalidSignature(f"Unable to evaluate type annotation {annotation}")

    return annotation


def _create_field(
    param: inspect.Parameter, annotation_type: Any
) -> tuple[Any, FieldInfo]:
    """
    Create a Pydantic field for a function parameter.

    Args:
        param (inspect.Parameter): The parameter to create a field for.
        annotation_type (Any): The type annotation for the parameter.

    Returns:
        tuple[Any, FieldInfo]: A tuple of the annotated type and the field info.
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


def _generate_parameters_model(func: Callable) -> Optional[type[ArgModelBase]]:
    """
    Generate a JSON Schema-compliant schema for the function's parameters.

    Args:
        func (Callable): The function to generate the schema for.

    Returns:
        Optional[type[ArgModelBase]]: The Pydantic model representing the function's parameters,
        or None if an error occurs.
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
