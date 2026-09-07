import inspect
import typing
import warnings
from enum import Enum
from typing import Any, Literal, Union, get_type_hints
from collections.abc import Callable

from ._vendor.validate import (
    Doc,
    Ge,
    Gt,
    Le,
    Lt,
    MaxLen,
    MinLen,
    create_struct,
    json_schema as _json_schema,
)


class InvalidSignature(Exception):
    """Exception raised when a function signature cannot be processed.

    Attributes:
        message (str): Explanation of the error.
    """


def _get_typed_annotation(annotation: Any, globalns: dict[str, Any]) -> Any:
    """Evaluate type annotation, handling forward references.

    Uses Python's public get_type_hints function rather than relying on
    a framework-specific internal function.

    Args:
        annotation (Any): The annotation to evaluate (can be string forward reference).
        globalns (Dict[str, Any]): The global namespace to use for evaluating the annotation.

    Returns:
        Any: The evaluated annotation.

    Raises:
        InvalidSignature: If unable to evaluate type annotation.
    """

    if isinstance(annotation, str):

        def dummy(a: Any):
            pass

        dummy.__annotations__ = {"a": annotation}
        try:
            hints = get_type_hints(dummy, globalns, include_extras=True)
            return hints["a"]
        except Exception as e:
            raise InvalidSignature(
                f"Unable to evaluate type annotation {annotation}"
            ) from e

    return annotation


def _create_field(param: inspect.Parameter, annotation_type: Any) -> tuple[Any, Any]:
    """Create a field definition for a function parameter.

    Returns:
        Tuple of (type, default) where default is ``...`` for required fields.
    """
    if param.default is inspect.Parameter.empty:
        return (annotation_type, ...)
    else:
        default = param.default
        if param.annotation is inspect.Parameter.empty:
            return (annotation_type | None, default)
        else:
            return (annotation_type, default)


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


def _is_json_schema_compatible(param_name: str, field_def: tuple[Any, Any]) -> bool:
    """Return whether a single field can produce JSON Schema."""
    annotation_type = field_def[0]
    if annotation_type is Any:
        return True
    try:
        struct = create_struct(f"_{param_name}Probe", {param_name: field_def})
        schema = _json_schema(struct)
        props = schema.get("properties", {})
        if param_name in props and props[param_name] == {}:
            return False
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


_CONSTRAINT_MAP: dict[str, type] = {
    "ge": Ge,
    "gt": Gt,
    "le": Le,
    "lt": Lt,
    "max_length": MaxLen,
    "min_length": MinLen,
}


def _translate_single_meta(arg: Any) -> list[Any]:
    """Convert one Annotated metadata item to zerodep equivalents."""
    if isinstance(arg, (Ge, Gt, Le, Lt, MaxLen, MinLen, Doc)):
        return [arg]

    matched: list[Any] = []
    for attr, cls in _CONSTRAINT_MAP.items():
        val = getattr(arg, attr, None)
        if val is not None:
            matched.append(cls(val))
    if matched:
        return matched

    if hasattr(arg, "metadata") and hasattr(arg, "description"):
        result: list[Any] = []
        if arg.description:
            result.append(Doc(arg.description))
        for m in getattr(arg, "metadata", []):
            result.extend(_translate_single_meta(m))
        return result

    if hasattr(arg, "check") or hasattr(arg, "schema_kw"):
        return [arg]

    return []


def _translate_annotated_metadata(annotation: Any) -> Any:
    """Translate Pydantic/annotated_types constraints to zerodep equivalents."""
    if typing.get_origin(annotation) is not typing.Annotated:
        return annotation

    args = typing.get_args(annotation)
    base = args[0]
    new_meta: list[Any] = []
    for arg in args[1:]:
        new_meta.extend(_translate_single_meta(arg))

    if new_meta:
        return typing.Annotated[tuple([base] + new_meta)]
    return base


def _resolve_enum(annotation: Any) -> Any:
    """Convert Enum subclass annotations to Literal equivalents.

    Recurses into Union/Optional so that ``Optional[MyEnum]`` becomes
    ``Optional[Literal[...]]``.
    """
    origin = typing.get_origin(annotation)
    if origin is Union:
        args = tuple(_resolve_enum(a) for a in typing.get_args(annotation))
        return Union[args]  # type: ignore[valid-type]
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        values = tuple(e.value for e in annotation)
        return Literal[values]  # type: ignore[valid-type]  # ty: ignore[invalid-type-form]
    return annotation


def _field_def_for_parameter(
    func: Callable,
    param: inspect.Parameter,
    globalns: dict[str, Any],
    resolved_hints: dict[str, Any],
) -> tuple[Any, Any]:
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
            annotation = _resolve_enum(annotation)
            annotation = _translate_annotated_metadata(annotation)
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
    """Collapse nullable schema patterns into simpler forms.

    Handles two patterns:
    - Pydantic v2: ``anyOf: [{type: T}, {type: null}]`` → ``type: T``
    - zerodep:     ``type: [T, "null"]`` → ``type: T``

    This function mutates *schema* in place and returns it.

    Args:
        schema: A JSON Schema dict.

    Returns:
        The same dict with nullable patterns simplified.
    """
    props = schema.get("properties")
    if not props:
        return schema

    for prop_schema in props.values():
        # Handle anyOf pattern (Pydantic v2 style)
        any_of = prop_schema.get("anyOf")
        if any_of and isinstance(any_of, list):
            non_null = [v for v in any_of if v != {"type": "null"}]
            if len(non_null) < len(any_of):
                if len(non_null) == 1:
                    del prop_schema["anyOf"]
                    prop_schema.update(non_null[0])
                else:
                    prop_schema["anyOf"] = non_null

        # Handle type-array pattern (zerodep style): type: ["string", "null"]
        type_val = prop_schema.get("type")
        if isinstance(type_val, list) and "null" in type_val:
            non_null_types = [t for t in type_val if t != "null"]
            if len(non_null_types) == 1:
                prop_schema["type"] = non_null_types[0]
            elif len(non_null_types) > 1:
                prop_schema["type"] = non_null_types

    return schema


def _create_parameters_model(
    func: Callable,
    field_definitions: dict[str, tuple[Any, Any]],
    *,
    has_var_keyword: bool = False,
) -> type | None:
    """Create and validate the final parameter struct type."""
    try:
        struct = create_struct(
            f"{getattr(func, '__name__', 'unknown')}Parameters",
            field_definitions,
        )
        struct._has_var_keyword = has_var_keyword  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        _json_schema(struct)
        return struct
    except Exception:
        return None


def _generate_parameters_model(func: Callable) -> type | None:
    """Generate a type from a function's parameters for validation and schema.

    Creates a TypedDict-based type that can validate the function's parameters
    and produce JSON Schema.

    Args:
        func (Callable): The function to generate the parameter model for.

    Returns:
        Optional[type]: TypedDict type for the parameters, or None on error.

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

    field_definitions: dict[str, tuple[Any, Any]] = {}
    has_var_keyword = False
    for param in signature.parameters.values():
        if param.name == "self":
            continue
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            _warn_skipped_variadic_parameter(func, param)
            continue
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            has_var_keyword = True
            continue
        field_definitions[param.name] = _field_def_for_parameter(
            func,
            param,
            globalns,
            resolved_hints,
        )

    return _create_parameters_model(
        func, field_definitions, has_var_keyword=has_var_keyword
    )
