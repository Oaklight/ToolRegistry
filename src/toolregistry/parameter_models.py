import inspect
import json
import types
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


#: Bare containers and the parametrized form that renders as a typed node.
#:
#: A bare container has no element type, so the schema backend renders it as
#: an unconstrained ``{}``.  Inside a union that branch either disappears
#: (``T | None`` collapses to nothing) or matches every value, which makes the
#: whole ``anyOf`` vacuous.  The ``typing`` aliases (``typing.List`` and
#: friends) have the same problem when their ``__args__`` are empty.
_BARE_CONTAINERS: dict[Any, Any] = {
    list: list[Any],
    dict: dict[Any, Any],
    set: set[Any],
    frozenset: frozenset[Any],
    tuple: tuple[Any, ...],
}


def _normalize_bare_containers(annotation: Any) -> Any:
    """Parameterize containers that were annotated without arguments.

    Only annotations that name a container with no element type are rewritten;
    parameterized forms are returned untouched.  The rewrite recurses through
    unions, so a bare container branch keeps its container identity next to
    the other branches of ``X | Y``.

    Args:
        annotation: A resolved type annotation.

    Returns:
        The annotation with bare containers parameterized by ``Any``.
    """
    replacement = _BARE_CONTAINERS.get(annotation)
    if replacement is not None:
        return replacement

    origin = typing.get_origin(annotation)
    if origin in _BARE_CONTAINERS and not typing.get_args(annotation):
        return _BARE_CONTAINERS[origin]

    if origin in (Union, types.UnionType):
        args = tuple(_normalize_bare_containers(a) for a in typing.get_args(annotation))
        return Union[args]  # type: ignore[valid-type]
    return annotation


def _resolve_enum(annotation: Any) -> Any:
    """Convert Enum subclass annotations to Literal equivalents.

    Recurses into Union/Optional so that ``Optional[MyEnum]`` becomes
    ``Optional[Literal[...]]``.
    """
    origin = typing.get_origin(annotation)
    if origin in (Union, types.UnionType):
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
    degraded: set[str] | None = None,
) -> tuple[Any, Any]:
    """Create a schema-safe field definition for one parameter.

    Args:
        func: Function being inspected.
        param: The parameter.
        globalns: The function's globals, for annotation resolution.
        resolved_hints: Resolved type hints for the function.
        degraded: Optional set that receives the names of parameters whose
            annotation already produced a fallback warning, so the later
            untyped-schema diagnostic does not repeat the symptom.
    """
    if param.annotation is inspect.Parameter.empty:
        field_def = _create_field(param, Any)
    elif param.annotation is None:
        field_def = _create_field(param, None)
    else:
        try:
            annotation = resolved_hints.get(param.name)
            if annotation is None:
                annotation = _get_typed_annotation(param.annotation, globalns)
            annotation = _normalize_bare_containers(annotation)
            annotation = _resolve_enum(annotation)
            annotation = _translate_annotated_metadata(annotation)
            field_def = _create_field(param, annotation)
        except Exception as e:
            _warn_parameter_fallback(func, param.name, e)
            if degraded is not None:
                degraded.add(param.name)
            field_def = _create_field(param, Any)

    if _is_json_schema_compatible(param.name, field_def):
        return field_def

    _warn_parameter_fallback(
        func,
        param.name,
        InvalidSignature(f"unsupported annotation {param.annotation!r}"),
    )
    if degraded is not None:
        degraded.add(param.name)
    return _create_field(param, Any)


def _normalize_union_keywords(schema: dict[str, Any]) -> dict[str, Any]:
    """Rewrite annotation-derived ``oneOf`` unions to inclusive ``anyOf``.

    The schema backend renders Python unions as ``oneOf``, but ``X | Y`` is
    inclusive: a value may satisfy several branches (``int | float`` matches
    both).  ``oneOf`` requires exactly one match and would reject such values,
    so annotation-derived schemas are normalized to ``anyOf``.

    Only schemas generated from function annotations pass through here;
    caller-authored ``parameters=`` keep their original combination keyword.
    """
    map_keys = ("properties", "patternProperties", "dependentSchemas", "$defs")
    child_keys = (
        "items",
        "additionalProperties",
        "additionalItems",
        "contains",
        "not",
        "if",
        "then",
        "else",
        "propertyNames",
        "anyOf",
        "oneOf",
        "allOf",
        "prefixItems",
    )

    result = dict(schema)
    for key in map_keys:
        value = result.get(key)
        if isinstance(value, dict):
            result[key] = {
                name: _normalize_union_keywords(sub) for name, sub in value.items()
            }
    for key in child_keys:
        value = result.get(key)
        if isinstance(value, dict):
            result[key] = _normalize_union_keywords(value)
        elif isinstance(value, list):
            result[key] = [
                _normalize_union_keywords(sub) if isinstance(sub, dict) else sub
                for sub in value
            ]

    if "oneOf" in result and "anyOf" not in result:
        result["anyOf"] = result.pop("oneOf")
    return result


#: Schema keys whose value maps a name to a nested schema.
_SCHEMA_MAP_KEYS: tuple[str, ...] = (
    "properties",
    "patternProperties",
    "dependentSchemas",
    "$defs",
    "definitions",
)

#: Schema keys whose value is a nested schema or a list of them.
_SCHEMA_CHILD_KEYS: tuple[str, ...] = (
    "items",
    "additionalProperties",
    "additionalItems",
    "contains",
    "not",
    "if",
    "then",
    "else",
    "propertyNames",
    "prefixItems",
    "anyOf",
    "oneOf",
    "allOf",
)


def _canonical_schema_key(schema: Any) -> str:
    """Return a stable key used to recognize duplicate union branches."""
    return json.dumps(schema, sort_keys=True, separators=(",", ":"), default=str)


def _simplify_nested_schemas(schema: dict[str, Any]) -> None:
    """Apply the nullable/duplicate cleanup to every nested schema in *schema*."""
    for key in _SCHEMA_MAP_KEYS:
        value = schema.get(key)
        if isinstance(value, dict):
            for sub in value.values():
                if isinstance(sub, dict):
                    _simplify_nullable_schemas(sub)
    for key in _SCHEMA_CHILD_KEYS:
        value = schema.get(key)
        if isinstance(value, dict):
            _simplify_nullable_schemas(value)
        elif isinstance(value, list):
            _simplify_schema_list(value)


def _simplify_schema_list(schemas: list[Any]) -> None:
    """Apply the cleanup to each schema object in a list."""
    for sub in schemas:
        if isinstance(sub, dict):
            _simplify_nullable_schemas(sub)


def _simplify_union_branches(schema: dict[str, Any], keyword: str) -> None:
    """Drop null and duplicate branches from one union keyword in place."""
    variants = schema.get(keyword)
    if not isinstance(variants, list):
        return

    kept: list[Any] = []
    seen: set[str] = set()
    for variant in variants:
        if variant == {"type": "null"}:
            continue
        key = _canonical_schema_key(variant)
        if key in seen:
            continue
        seen.add(key)
        kept.append(variant)

    if kept == variants:
        return
    if not kept:
        # A union of only ``null`` is degenerate; keep the original rather
        # than deleting the only branch.
        return
    if len(kept) == 1:
        del schema[keyword]
        schema.update(kept[0])
    else:
        schema[keyword] = kept


def _simplify_type_array(schema: dict[str, Any]) -> None:
    """Remove ``"null"`` from a zerodep-style ``type: [T, "null"]`` list."""
    type_val = schema.get("type")
    if not isinstance(type_val, list) or "null" not in type_val:
        return
    non_null_types = [t for t in type_val if t != "null"]
    if len(non_null_types) == 1:
        schema["type"] = non_null_types[0]
    elif non_null_types:
        schema["type"] = non_null_types


def _simplify_nullable_schemas(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove null alternatives and duplicate union branches, recursively.

    Optional parameters are already represented by ``required`` and their
    default, so an explicit ``{"type": "null"}`` branch adds nothing.
    Duplicate branches are dropped as well: ``tuple`` and ``list[Any]`` both
    render as an untyped array, and keeping both inflates the payload without
    adding a distinguishable alternative.

    Unlike the previous top-level-only pass, this traverses nested schemas
    (array items, nested objects, ``$defs``) so a union behaves the same
    wherever it appears.

    This function mutates *schema* in place and returns it.

    Args:
        schema: A JSON Schema dict.

    Returns:
        The same dict with null alternatives and duplicate branches removed.
    """
    _simplify_nested_schemas(schema)
    for keyword in ("anyOf", "oneOf"):
        _simplify_union_branches(schema, keyword)
    _simplify_type_array(schema)
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
    annotations: dict[str, Any] = {}
    degraded: set[str] = set()
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
        annotations[param.name] = resolved_hints.get(param.name, param.annotation)
        field_definitions[param.name] = _field_def_for_parameter(
            func,
            param,
            globalns,
            resolved_hints,
            degraded=degraded,
        )

    model = _create_parameters_model(
        func, field_definitions, has_var_keyword=has_var_keyword
    )
    if model is not None:
        # Kept for the post-normalization diagnostic: once the schema has been
        # flattened, the original annotation is the only way to tell a
        # deliberate ``Any`` from a degraded bare container.
        model._parameter_annotations = annotations  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        model._degraded_parameter_names = degraded  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    return model


#: Keys that make a schema node typed or explicitly unconstrained.
_TYPED_SCHEMA_KEYS: frozenset[str] = frozenset(
    {"type", "$ref", "enum", "const", "anyOf", "oneOf", "allOf", "not"}
)


def _is_untyped_schema(node: Any) -> bool:
    """Return True when *node* carries no type information at all."""
    if not isinstance(node, dict):
        return False
    return not (node.keys() & _TYPED_SCHEMA_KEYS)


def _is_any_like(annotation: Any) -> bool:
    """Return True when an unconstrained schema is correct for *annotation*.

    ``Any``, ``object``, and an optional form of either (``Any | None``)
    legitimately render as an empty schema; they are not a degradation.
    """
    if annotation in (typing.Any, object, inspect.Parameter.empty):
        return True
    origin = typing.get_origin(annotation)
    if origin in (Union, types.UnionType):
        non_null = [a for a in typing.get_args(annotation) if a is not type(None)]
        return all(_is_any_like(a) for a in non_null)
    return False


def warn_untyped_parameters(
    func_name: str,
    parameters_schema: dict[str, Any],
    annotations: dict[str, Any],
    already_warned: set[str] | None = None,
) -> None:
    """Warn when a parameter renders without a type in the JSON Schema.

    An empty schema tells a schema-driven client nothing about what to send.
    The usual causes are a bare container that escaped normalization and an
    annotation the backend cannot express; both used to degrade silently.
    ``Any``, ``object``, and unannotated parameters are excluded because an
    unconstrained schema is the correct rendering for them.

    Args:
        func_name: Name used in the warning message.
        parameters_schema: The final ``Tool.parameters`` schema.
        annotations: Original resolved annotations, keyed by parameter name.
        already_warned: Parameters whose annotation already produced a
            specific fallback warning; the generic diagnostic is skipped for
            them so one mistake does not produce two warnings.
    """
    properties = parameters_schema.get("properties")
    if not isinstance(properties, dict):
        return
    skip = already_warned or set()
    for name, prop in properties.items():
        if name not in annotations or name in skip:
            continue
        annotation = annotations[name]
        if _is_any_like(annotation):
            continue
        untyped = _is_untyped_schema(prop)
        untyped_branch = isinstance(prop, dict) and any(
            _is_untyped_schema(branch)
            for keyword in ("anyOf", "oneOf")
            for branch in prop.get(keyword, [])
        )
        if untyped or untyped_branch:
            warnings.warn(
                f"Parameter '{name}' of '{func_name}' renders without a type "
                "in its JSON Schema, so schema-driven clients cannot build a "
                "valid value. Annotate the element type (for example "
                "list[float] instead of list).",
                UserWarning,
                stacklevel=3,
            )
