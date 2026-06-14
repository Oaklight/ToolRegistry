import inspect
import warnings
from typing import Any, get_type_hints
from collections.abc import Callable

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

    def model_dump_one_level(self) -> dict[str, Any]:
        """Dump model fields one level deep, keeping sub-models as-is.

        Returns:
            Dict[str, Any]: Dictionary of field names to values.
        """
        return {field: getattr(self, field) for field in self.__pydantic_fields__}

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


def _get_typed_annotation(annotation: Any, globalns: dict[str, Any]) -> Any:
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
            hints = get_type_hints(dummy, globalns, include_extras=True)
            return hints["a"]
        except Exception as e:
            raise InvalidSignature(
                f"Unable to evaluate type annotation {annotation}"
            ) from e

    return annotation


def _create_field(
    param: inspect.Parameter, annotation_type: Any
) -> tuple[Any, FieldInfo]:
    """Create a Pydantic field for a function parameter.

    Handles both annotated and unannotated parameters, with and without defaults.

    Args:
        param (inspect.Parameter): The parameter to create a field for.
        annotation_type (Any): The type annotation for the parameter.

    Returns:
        Tuple[Any, FieldInfo]: A tuple of (annotated_type, field_info).
    """
    if param.default is inspect.Parameter.empty:
        if param.annotation is inspect.Parameter.empty:
            field_info = Field(title=param.name)
        else:
            field_info = Field()
        return (annotation_type, field_info)
    else:
        default = param.default
        if param.annotation is inspect.Parameter.empty:
            field_info = Field(default=default, title=param.name)
            # No annotation — allow None since we can't infer intent.
            return (annotation_type | None, field_info)
        else:
            field_info = Field(default=default)
            # Respect the user's declared type. If they wrote `str | None`,
            # annotation_type already includes None. Don't force-add it.
            return (annotation_type, field_info)


def _warn_parameter_fallback(
    func: Callable, param_name: str, reason: Exception
) -> None:
    """Warn that a parameter annotation fell back to ``Any``."""
    warnings.warn(
        f"Parameter '{param_name}' in '{getattr(func, '__name__', '<unknown>')}' "
        f"has an annotation that cannot be represented in JSON Schema: {reason}. "
        "Falling back to an unconstrained schema for this parameter.",
        UserWarning,
        stacklevel=3,
    )


def _is_json_schema_compatible(
    param_name: str, field_def: tuple[Any, FieldInfo]
) -> bool:
    """Return whether a single field can produce JSON Schema."""
    try:
        field_definitions: dict[str, Any] = {param_name: field_def}
        test_model = create_model(
            f"_{param_name}SchemaProbe",
            **field_definitions,
            __base__=ArgModelBase,
        )
        test_model.model_json_schema()
        return True
    except Exception:
        return False


def _warn_skipped_variadic_parameter(func: Callable, param: inspect.Parameter) -> None:
    """Warn that a variadic parameter is excluded from the schema."""
    label = (
        f"*{param.name}"
        if param.kind == inspect.Parameter.VAR_POSITIONAL
        else f"**{param.name}"
    )
    kind = "*args" if param.kind == inspect.Parameter.VAR_POSITIONAL else "**kwargs"
    warnings.warn(
        f"Parameter '{label}' ({kind}) in "
        f"'{getattr(func, '__name__', '<unknown>')}' is not "
        "representable in JSON Schema and will be excluded "
        "from the tool schema.",
        UserWarning,
        stacklevel=2,
    )


def _field_def_for_parameter(
    func: Callable,
    param: inspect.Parameter,
    globalns: dict[str, Any],
    resolved_hints: dict[str, Any],
) -> tuple[Any, FieldInfo]:
    """Create a schema-safe field definition for one parameter."""
    if param.annotation is inspect.Parameter.empty:
        field_def = _create_field(param, Any)
    elif param.annotation is None:
        field_def = _create_field(param, None)
    else:
        try:
            annotation = resolved_hints.get(param.name)
            if annotation is None:
                annotation = _get_typed_annotation(param.annotation, globalns)
            field_def = _create_field(param, annotation)
        except Exception as e:
            _warn_parameter_fallback(func, param.name, e)
            field_def = _create_field(param, Any)

    if _is_json_schema_compatible(param.name, field_def):
        return field_def

    _warn_parameter_fallback(
        func,
        param.name,
        InvalidSignature(f"unsupported annotation {param.annotation!r}"),
    )
    return _create_field(param, Any)


def _simplify_nullable_schemas(schema: dict[str, Any]) -> dict[str, Any]:
    """Collapse ``anyOf: [{type: T}, {type: null}]`` into ``type: T``.

    Pydantic v2 emits ``anyOf`` for ``Optional`` / ``T | None`` fields.
    MCP clients (e.g. Claude Code) display these as "unknown" because they
    don't resolve ``anyOf``.  Since optional parameters are already
    expressed by omitting them from ``required`` and having a ``default``,
    the ``null`` variant adds no information and can be safely removed.

    This function mutates *schema* in place and returns it.

    Args:
        schema: A JSON Schema dict (output of ``model_json_schema()``).

    Returns:
        The same dict with nullable ``anyOf`` patterns simplified.
    """
    props = schema.get("properties")
    if not props:
        return schema

    for prop_schema in props.values():
        any_of = prop_schema.get("anyOf")
        if not any_of or not isinstance(any_of, list):
            continue
        non_null = [v for v in any_of if v != {"type": "null"}]
        if len(non_null) == len(any_of):
            continue  # no null branch — nothing to simplify
        if len(non_null) == 1:
            # Simple nullable: [{type: T}, {type: null}] → type: T
            del prop_schema["anyOf"]
            prop_schema.update(non_null[0])
        else:
            # Multi-type nullable: [{type: T1}, {type: T2}, {type: null}]
            # → anyOf: [{type: T1}, {type: T2}] (null branch removed)
            prop_schema["anyOf"] = non_null
        prop_schema["nullable"] = True

    return schema


def _create_parameters_model(
    func: Callable,
    field_definitions: dict[str, Any],
) -> type[ArgModelBase] | None:
    """Create and validate the final Pydantic parameter model."""
    try:
        model = create_model(
            f"{getattr(func, '__name__', 'unknown')}Parameters",
            **field_definitions,
            __base__=ArgModelBase,
        )
        model.model_json_schema()
        return model
    except Exception:
        return None


def _generate_parameters_model(func: Callable) -> type[ArgModelBase] | None:
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
    except Exception:
        return None

    globalns = getattr(func, "__globals__", {})
    try:
        resolved_hints = get_type_hints(func, globalns, include_extras=True)
    except Exception:
        resolved_hints = {}

    field_definitions: dict[str, Any] = {}
    for param in signature.parameters.values():
        if param.name == "self":
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            _warn_skipped_variadic_parameter(func, param)
            continue
        field_definitions[param.name] = _field_def_for_parameter(
            func,
            param,
            globalns,
            resolved_hints,
        )

    return _create_parameters_model(func, field_definitions)
