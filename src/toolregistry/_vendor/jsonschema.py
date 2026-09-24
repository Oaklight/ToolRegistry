# /// zerodep
# version = "0.4.1"
# deps = []
# tier = "subsystem"
# category = "validation"
# note = "Install/update via: https://zerodep.readthedocs.io/en/latest/guide/cli/"
# ///
"""JSON Schema flattening, sanitization & validation — zero dependencies, stdlib only.

Flatten complex JSON Schemas for LLM providers, and validate data instances
against JSON Schema (Draft 2020-12 subset used by OpenAPI 3.x).

Part of zerodep: https://github.com/Oaklight/zerodep
Copyright (c) 2026 Peng Ding. MIT License.

Flattening example::

    >>> from jsonschema import flatten_schema
    >>> schema = {
    ...     "type": "object",
    ...     "properties": {
    ...         "user": {"$ref": "#/$defs/User"},
    ...     },
    ...     "$defs": {
    ...         "User": {
    ...             "type": "object",
    ...             "properties": {"name": {"type": "string"}},
    ...         }
    ...     },
    ... }
    >>> flatten_schema(schema)
    {'type': 'object', 'properties': {'user': {'type': 'object', 'properties': {'name': {'type': 'string'}}}}}

Validation example::

    >>> from jsonschema import schema_validate, iter_errors
    >>> schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    >>> schema_validate({"name": "Alice"}, schema)
    >>> errors = iter_errors({}, schema)
    >>> len(errors)
    1

Supported validation keywords (Draft 2020-12 subset)::

    type, enum, const,
    minLength, maxLength, pattern,
    minimum, maximum, exclusiveMinimum, exclusiveMaximum, multipleOf,
    properties, required, additionalProperties, patternProperties,
    minProperties, maxProperties,
    items, prefixItems, minItems, maxItems, uniqueItems, contains,
    allOf, anyOf, oneOf, not, if/then/else

Not implemented: dependentRequired, dependentSchemas, propertyNames,
minContains, maxContains, format.

Note: OpenAPI 3.0 ``nullable: true`` is not handled by the validator.
Use ``flatten_schema`` to convert ``nullable`` to ``type: [..., "null"]``
before validating, or write schemas using Draft 2020-12 type arrays.

Flattening pipeline::

    resolve_refs  →  merge_allof  →  simplify_unions  →  sanitize
"""

from __future__ import annotations

import copy
import dataclasses
import math
import re
import warnings
from typing import Any

__all__ = [
    # Schema transformation
    "flatten_schema",
    "resolve_refs",
    "merge_allof",
    "simplify_unions",
    "sanitize",
    "UNSUPPORTED_SCHEMA_KEYS",
    # Schema validation
    "schema_validate",
    "iter_errors",
    "SchemaErrorDetail",
    "SchemaValidationError",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFS_KEYS: set[str] = {"$defs", "definitions"}

# Keys whose *values* are property-name maps (not schema nodes).
# When a walker enters one of these, it must NOT treat the map's keys as
# schema keywords — they are user-defined parameter names.  The map's
# *values* are sub-schemas and should still be processed.
_PROPERTY_MAP_KEYS: set[str] = {"properties", "patternProperties", "dependentSchemas"}

UNSUPPORTED_SCHEMA_KEYS: set[str] = {
    # JSON Schema meta
    "$schema",
    "$id",
    "$comment",
    "$anchor",
    "$dynamicAnchor",
    "$dynamicRef",
    # content keywords
    "contentEncoding",
    "contentMediaType",
    "contentSchema",
    # documentation / status
    "deprecated",
    "readOnly",
    "writeOnly",
    "examples",
    # constraints most LLM providers reject
    "propertyNames",
    "const",
}

# Numeric constraint merge rules: keyword → "take_max" or "take_min".
# allOf semantics = intersection ⇒ lower-bounds tighten up (max), upper-bounds tighten down (min).
_LOWER_BOUND_KEYS: set[str] = {
    "minimum",
    "exclusiveMinimum",
    "minLength",
    "minItems",
    "minProperties",
}
_UPPER_BOUND_KEYS: set[str] = {
    "maximum",
    "exclusiveMaximum",
    "maxLength",
    "maxItems",
    "maxProperties",
}

# ---------------------------------------------------------------------------
# Phase 1 — $ref resolution
# ---------------------------------------------------------------------------


def _collect_defs(schema: dict[str, Any]) -> dict[str, Any]:
    """Collect all entries from ``$defs`` and ``definitions`` maps."""
    defs: dict[str, Any] = {}
    for key in _DEFS_KEYS:
        d = schema.get(key)
        if isinstance(d, dict):
            defs.update(d)
    return defs


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    """Resolve a ``$ref`` JSON Pointer against the document *root*.

    Supports any local JSON Pointer (RFC 6901) fragment, e.g.
    ``#/$defs/Name``, ``#/definitions/Name``, ``#/components/schemas/Foo``.
    Returns ``{}`` for unresolvable or non-dict targets.
    """
    if not ref.startswith("#/"):
        return {}
    pointer = ref[2:]  # strip "#/"
    segments = [s.replace("~1", "/").replace("~0", "~") for s in pointer.split("/")]
    node: Any = root
    for seg in segments:
        if isinstance(node, dict) and seg in node:
            node = node[seg]
        else:
            return {}
    return node if isinstance(node, dict) else {}


def _inline_refs(
    schema: dict[str, Any],
    root: dict[str, Any],
    _seen: set[str] | None = None,
) -> dict[str, Any]:
    """Recursively inline all ``$ref`` pointers in *schema*.

    *root* is the top-level document used for JSON Pointer resolution.
    *_seen* tracks ``$ref`` strings on the current resolution stack to
    prevent infinite recursion from circular references.
    """
    if _seen is None:
        _seen = set()

    ref = schema.get("$ref")
    if isinstance(ref, str):
        if ref in _seen:
            # Circular reference — drop the $ref and keep sibling keys.
            warnings.warn(
                f"Circular $ref: {ref!r} — dropped",
                stacklevel=2,
            )
            return {k: v for k, v in schema.items() if k != "$ref"}
        resolved = _resolve_ref(ref, root)
        if resolved:
            _seen = _seen | {ref}  # new set — don't mutate caller's copy
            merged = {**copy.deepcopy(resolved)}
            for k, v in schema.items():
                if k != "$ref":
                    merged[k] = v
            return _inline_refs(merged, root, _seen)
        else:
            warnings.warn(
                f"Unresolvable $ref: {ref!r} — dropped",
                stacklevel=2,
            )
            return {k: v for k, v in schema.items() if k != "$ref"}

    # No $ref at this level — recurse into children.
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            result[key] = _inline_refs(value, root, _seen)
        elif isinstance(value, list):
            result[key] = [
                _inline_refs(item, root, _seen) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def resolve_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve all local ``$ref`` pointers and inline their targets.

    Supports any JSON Pointer fragment (RFC 6901), including
    ``#/$defs/``, ``#/definitions/``, ``#/components/schemas/``, etc.
    After resolution, ``$defs`` and ``definitions`` maps are removed.

    Args:
        schema: A JSON Schema dict.

    Returns:
        A new dict with all ``$ref`` inlined and definition maps removed.
    """
    schema = copy.deepcopy(schema)
    result = _inline_refs(schema, schema)
    # Strip consumed definition maps.
    for key in _DEFS_KEYS:
        result.pop(key, None)
    return result


# ---------------------------------------------------------------------------
# Phase 2 — allOf merging
# ---------------------------------------------------------------------------


def _deep_merge_two(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge *override* into *base* using allOf intersection semantics.

    - ``properties``: recursively merge per-property schemas.
    - ``required``: union (deduplicated).
    - ``type``: intersect.
    - Numeric constraints: tighten (lower-bounds ↑, upper-bounds ↓).
    - ``enum``: intersect.
    - ``items``, ``additionalProperties``: recursive merge if both dicts.
    - Everything else: *override* wins.
    """
    merged = dict(base)  # shallow start — keys are replaced below as needed

    for key, oval in override.items():
        if key not in merged:
            merged[key] = oval
            continue

        bval = merged[key]

        if key == "properties" and isinstance(bval, dict) and isinstance(oval, dict):
            props = dict(bval)
            for pname, pschema in oval.items():
                if (
                    pname in props
                    and isinstance(props[pname], dict)
                    and isinstance(pschema, dict)
                ):
                    props[pname] = _deep_merge_two(props[pname], pschema)
                else:
                    props[pname] = pschema
            merged[key] = props

        elif key == "required" and isinstance(bval, list) and isinstance(oval, list):
            merged[key] = list(dict.fromkeys(bval + oval))  # union, order-preserving

        elif key == "type":
            merged[key] = _intersect_type(bval, oval)

        elif key in _LOWER_BOUND_KEYS:
            # Tighten lower bound: take the larger value.
            if isinstance(bval, (int, float)) and isinstance(oval, (int, float)):
                merged[key] = max(bval, oval)
            else:
                merged[key] = oval

        elif key in _UPPER_BOUND_KEYS:
            # Tighten upper bound: take the smaller value.
            if isinstance(bval, (int, float)) and isinstance(oval, (int, float)):
                merged[key] = min(bval, oval)
            else:
                merged[key] = oval

        elif key == "enum" and isinstance(bval, list) and isinstance(oval, list):
            merged[key] = [v for v in bval if v in oval] or oval

        elif (
            key in ("items", "additionalProperties")
            and isinstance(bval, dict)
            and isinstance(oval, dict)
        ):
            merged[key] = _deep_merge_two(bval, oval)

        else:
            merged[key] = oval

    return merged


def _intersect_type(a: str | list[str], b: str | list[str]) -> str | list[str]:
    """Intersect two JSON Schema ``type`` values."""
    sa = {a} if isinstance(a, str) else set(a)
    sb = {b} if isinstance(b, str) else set(b)
    common = sa & sb
    if not common:
        # No intersection — fall back to *a* (caller's base).
        return a
    if len(common) == 1:
        return next(iter(common))
    return sorted(common)


def _merge_allof_node(schema: dict[str, Any]) -> dict[str, Any]:
    """Merge a single ``allOf`` array into one schema, including sibling keys."""
    all_of = schema["allOf"]
    # Start with sibling keys (everything except ``allOf``).
    base: dict[str, Any] = {k: v for k, v in schema.items() if k != "allOf"}
    for sub in all_of:
        if isinstance(sub, dict):
            base = _deep_merge_two(base, sub)
    return base


def _walk_merge_allof(
    schema: dict[str, Any],
    *,
    _in_property_map: bool = False,
) -> dict[str, Any]:
    """Recursively merge all ``allOf`` nodes in *schema*."""
    # First recurse into children so nested allOf are resolved bottom-up.
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            result[key] = _walk_merge_allof(
                value, _in_property_map=key in _PROPERTY_MAP_KEYS
            )
        elif isinstance(value, list):
            result[key] = [
                _walk_merge_allof(item, _in_property_map=False)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            result[key] = value

    if not _in_property_map and "allOf" in result and isinstance(result["allOf"], list):
        result = _merge_allof_node(result)
    return result


def merge_allof(schema: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge all ``allOf`` sub-schemas into single schemas.

    Args:
        schema: A JSON Schema dict (``$ref`` should be resolved first).

    Returns:
        A new dict with all ``allOf`` keywords resolved.
    """
    return _walk_merge_allof(copy.deepcopy(schema))


# ---------------------------------------------------------------------------
# Phase 3 — anyOf / oneOf simplification
# ---------------------------------------------------------------------------


def _simplify_node(schema: dict[str, Any]) -> dict[str, Any]:
    """Simplify a single ``anyOf`` or ``oneOf`` node."""
    for keyword in ("anyOf", "oneOf"):
        variants = schema.get(keyword)
        if not isinstance(variants, list):
            continue

        non_null = [v for v in variants if v.get("type") != "null"]
        has_null = len(non_null) < len(variants)

        # Sibling keys (description, title, etc.) form the base.
        base: dict[str, Any] = {
            k: v for k, v in schema.items() if k not in ("anyOf", "oneOf")
        }

        if len(non_null) == 1:
            base = _deep_merge_two(base, non_null[0])
        elif len(non_null) > 1:
            base["anyOf"] = non_null
        # else: all null — base stays as-is

        if has_null:
            base["nullable"] = True

        return base

    return schema


def _walk_simplify(
    schema: dict[str, Any],
    *,
    _in_property_map: bool = False,
) -> dict[str, Any]:
    """Recursively simplify all ``anyOf``/``oneOf`` nodes."""
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            result[key] = _walk_simplify(
                value, _in_property_map=key in _PROPERTY_MAP_KEYS
            )
        elif isinstance(value, list):
            result[key] = [
                _walk_simplify(item, _in_property_map=False)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            result[key] = value

    if not _in_property_map and result.keys() & {"anyOf", "oneOf"}:
        result = _simplify_node(result)
    return result


def simplify_unions(schema: dict[str, Any]) -> dict[str, Any]:
    """Simplify ``anyOf``/``oneOf`` constructs.

    - Nullable pattern ``[{type: T}, {type: null}]`` → ``{type: T, nullable: true}``
    - Single-variant: unwrap.
    - Multi-variant with null: strip the ``{type: null}`` branch, keep remaining
      branches as ``anyOf``.

    Args:
        schema: A JSON Schema dict.

    Returns:
        A new dict with ``anyOf``/``oneOf`` simplified.
    """
    return _walk_simplify(copy.deepcopy(schema))


# ---------------------------------------------------------------------------
# Phase 4 — Sanitization & validation
# ---------------------------------------------------------------------------


def _walk_sanitize(
    schema: dict[str, Any],
    strip: set[str],
    *,
    _in_property_map: bool = False,
) -> dict[str, Any]:
    """Recursively strip unsupported keys and prune orphaned ``required``."""
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if not _in_property_map and key in strip:
            continue
        if isinstance(value, dict):
            result[key] = _walk_sanitize(
                value, strip, _in_property_map=key in _PROPERTY_MAP_KEYS
            )
        elif isinstance(value, list):
            result[key] = [
                _walk_sanitize(item, strip, _in_property_map=False)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            result[key] = value

    # Prune required ⊆ properties.
    if "required" in result and "properties" in result:
        props = result["properties"]
        pruned = [r for r in result["required"] if r in props]
        if pruned:
            result["required"] = pruned
        else:
            del result["required"]

    return result


def sanitize(
    schema: dict[str, Any],
    *,
    strip_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Strip unsupported schema keywords and validate ``required`` arrays.

    Args:
        schema: A JSON Schema dict.
        strip_keys: Additional keys to strip beyond
            :data:`UNSUPPORTED_SCHEMA_KEYS`.

    Returns:
        A new dict with unsupported keys removed and ``required`` arrays
        pruned so that ``required ⊆ properties.keys()`` at every level.
    """
    strip = UNSUPPORTED_SCHEMA_KEYS | (strip_keys or set())
    return _walk_sanitize(copy.deepcopy(schema), strip)


# ---------------------------------------------------------------------------
# Phase 5 — Top-level API
# ---------------------------------------------------------------------------


def flatten_schema(
    schema: dict[str, Any],
    *,
    strip_keys: set[str] | None = None,
) -> dict[str, Any]:
    """One-call full pipeline: resolve → merge → simplify → sanitize.

    Args:
        schema: A JSON Schema dict, possibly containing ``$ref``,
            ``allOf``, ``anyOf``, ``oneOf``, and unsupported keywords.
        strip_keys: Additional keys to strip beyond
            :data:`UNSUPPORTED_SCHEMA_KEYS`.

    Returns:
        A flattened, sanitized schema safe for LLM provider consumption.
    """
    result = resolve_refs(schema)
    result = _walk_merge_allof(result)  # skip redundant deepcopy
    result = _walk_simplify(result)
    strip = UNSUPPORTED_SCHEMA_KEYS | (strip_keys or set())
    result = _walk_sanitize(result, strip)
    return result


# ---------------------------------------------------------------------------
# Phase 6 — Data validation
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class SchemaErrorDetail:
    """A single JSON Schema validation error.

    Attributes:
        path: Dotted/bracketed path to the failing instance location.
        schema_path: Dotted path into the schema that triggered the error.
        validator: The JSON Schema keyword that failed.
        message: Human-readable error message.
    """

    path: str
    schema_path: str
    validator: str
    message: str


class SchemaValidationError(Exception):
    """Raised when data validation against a JSON Schema fails.

    Attributes:
        errors: List of all validation errors found.
    """

    def __init__(self, errors: list[SchemaErrorDetail]) -> None:
        self.errors = errors
        msgs = "; ".join(e.message for e in errors[:5])
        if len(errors) > 5:
            msgs += f" ... and {len(errors) - 5} more"
        super().__init__(f"{len(errors)} schema validation error(s): {msgs}")


def _jp(base: str, key: str | int) -> str:
    """Join a path segment (dotted for strings, bracketed for indices)."""
    if isinstance(key, int):
        return f"{base}[{key}]" if base else f"[{key}]"
    return f"{base}.{key}" if base else key


_JSON_TYPE_CHECKS: dict[str, type | tuple[type, ...]] = {
    "null": type(None),
    "boolean": bool,
    "string": str,
    "array": list,
    "object": dict,
}


def _is_json_type(instance: Any, type_name: str) -> bool:
    """Check if *instance* matches the JSON Schema *type_name*."""
    if type_name == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if type_name == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    check = _JSON_TYPE_CHECKS.get(type_name)
    if check is None:
        return False
    return type(instance) is check if check is bool else isinstance(instance, check)


def _type_name(instance: Any) -> str:
    """Return the JSON Schema type name for a Python value."""
    if instance is None:
        return "null"
    if isinstance(instance, bool):
        return "boolean"
    if isinstance(instance, int):
        return "integer"
    if isinstance(instance, float):
        return "number"
    if isinstance(instance, str):
        return "string"
    if isinstance(instance, list):
        return "array"
    if isinstance(instance, dict):
        return "object"
    return type(instance).__name__


# -- Keyword handlers -------------------------------------------------------


def _check_type(
    instance: Any,
    type_val: str | list[str],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    """Validate the ``type`` keyword."""
    types = [type_val] if isinstance(type_val, str) else type_val
    if any(_is_json_type(instance, t) for t in types):
        return
    expected = type_val if isinstance(type_val, str) else types
    errors.append(
        SchemaErrorDetail(
            path=path or "$",
            schema_path=_jp(schema_path, "type"),
            validator="type",
            message=f"Expected type {expected} at '{path or '$'}', got {_type_name(instance)}",
        )
    )


def _check_enum(
    instance: Any,
    enum_val: list[Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    if not any(type(instance) is type(v) and instance == v for v in enum_val):
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "enum"),
                validator="enum",
                message=f"Value {instance!r} at '{path or '$'}' is not one of {enum_val}",
            )
        )


def _check_const(
    instance: Any,
    const_val: Any,
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    if type(instance) is not type(const_val) or instance != const_val:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "const"),
                validator="const",
                message=f"Value {instance!r} at '{path or '$'}' does not match const {const_val!r}",
            )
        )


def _check_string(
    instance: Any,
    schema: dict[str, Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    if not isinstance(instance, str):
        return
    if "minLength" in schema and len(instance) < schema["minLength"]:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "minLength"),
                validator="minLength",
                message=f"String at '{path or '$'}' is too short (length {len(instance)} < {schema['minLength']})",
            )
        )
    if "maxLength" in schema and len(instance) > schema["maxLength"]:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "maxLength"),
                validator="maxLength",
                message=f"String at '{path or '$'}' is too long (length {len(instance)} > {schema['maxLength']})",
            )
        )
    if "pattern" in schema and not re.search(schema["pattern"], instance):
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "pattern"),
                validator="pattern",
                message=f"String {instance!r} at '{path or '$'}' does not match pattern {schema['pattern']!r}",
            )
        )


def _check_number(
    instance: Any,
    schema: dict[str, Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    if not isinstance(instance, (int, float)) or isinstance(instance, bool):
        return
    if "minimum" in schema and instance < schema["minimum"]:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "minimum"),
                validator="minimum",
                message=f"Value {instance} at '{path or '$'}' is less than minimum {schema['minimum']}",
            )
        )
    if "maximum" in schema and instance > schema["maximum"]:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "maximum"),
                validator="maximum",
                message=f"Value {instance} at '{path or '$'}' is greater than maximum {schema['maximum']}",
            )
        )
    if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "exclusiveMinimum"),
                validator="exclusiveMinimum",
                message=f"Value {instance} at '{path or '$'}' must be > {schema['exclusiveMinimum']}",
            )
        )
    if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "exclusiveMaximum"),
                validator="exclusiveMaximum",
                message=f"Value {instance} at '{path or '$'}' must be < {schema['exclusiveMaximum']}",
            )
        )
    if "multipleOf" in schema:
        divisor = schema["multipleOf"]
        if isinstance(divisor, float) or isinstance(instance, float):
            quotient = instance / divisor
            if not math.isclose(quotient, round(quotient)):
                errors.append(
                    SchemaErrorDetail(
                        path=path or "$",
                        schema_path=_jp(schema_path, "multipleOf"),
                        validator="multipleOf",
                        message=f"Value {instance} at '{path or '$'}' is not a multiple of {divisor}",
                    )
                )
        elif instance % divisor != 0:
            errors.append(
                SchemaErrorDetail(
                    path=path or "$",
                    schema_path=_jp(schema_path, "multipleOf"),
                    validator="multipleOf",
                    message=f"Value {instance} at '{path or '$'}' is not a multiple of {divisor}",
                )
            )


def _check_object_props(
    instance: dict[str, Any],
    schema: dict[str, Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> set[str]:
    """Validate properties and patternProperties, return covered key names."""
    covered_keys: set[str] = set()
    properties = schema.get("properties", {})
    pattern_properties = schema.get("patternProperties", {})

    for prop_name, prop_schema in properties.items():
        if prop_name in instance:
            covered_keys.add(prop_name)
            if isinstance(prop_schema, (dict, bool)):
                _validate_schema(
                    instance[prop_name],
                    prop_schema,
                    errors,
                    _jp(path, prop_name),
                    _jp(schema_path, f"properties.{prop_name}"),
                )

    for pattern, pat_schema in pattern_properties.items():
        compiled = re.compile(pattern)
        for key in instance:
            if compiled.search(key):
                covered_keys.add(key)
                if isinstance(pat_schema, (dict, bool)):
                    _validate_schema(
                        instance[key],
                        pat_schema,
                        errors,
                        _jp(path, key),
                        _jp(schema_path, f"patternProperties.{pattern}"),
                    )

    return covered_keys


def _check_object(
    instance: Any,
    schema: dict[str, Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    if not isinstance(instance, dict):
        return

    if "required" in schema:
        for name in schema["required"]:
            if name not in instance:
                errors.append(
                    SchemaErrorDetail(
                        path=path or "$",
                        schema_path=_jp(schema_path, "required"),
                        validator="required",
                        message=f"Required property {name!r} is missing at '{path or '$'}'",
                    )
                )

    covered_keys = _check_object_props(instance, schema, errors, path, schema_path)

    if "additionalProperties" in schema:
        additional = schema["additionalProperties"]
        uncovered = set(instance.keys()) - covered_keys
        if additional is False:
            for key in sorted(uncovered):
                errors.append(
                    SchemaErrorDetail(
                        path=_jp(path, key),
                        schema_path=_jp(schema_path, "additionalProperties"),
                        validator="additionalProperties",
                        message=f"Additional property {key!r} is not allowed at '{_jp(path, key)}'",
                    )
                )
        elif isinstance(additional, dict):
            for key in sorted(uncovered):
                _validate_schema(
                    instance[key],
                    additional,
                    errors,
                    _jp(path, key),
                    _jp(schema_path, "additionalProperties"),
                )

    if "minProperties" in schema and len(instance) < schema["minProperties"]:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "minProperties"),
                validator="minProperties",
                message=f"Object at '{path or '$'}' has {len(instance)} properties, minimum is {schema['minProperties']}",
            )
        )
    if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "maxProperties"),
                validator="maxProperties",
                message=f"Object at '{path or '$'}' has {len(instance)} properties, maximum is {schema['maxProperties']}",
            )
        )


def _check_array_items(
    instance: list[Any],
    schema: dict[str, Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    """Validate prefixItems and items keywords."""
    prefix_items = schema.get("prefixItems")
    items_schema = schema.get("items")

    if prefix_items and isinstance(prefix_items, list):
        for i in range(min(len(prefix_items), len(instance))):
            pi_schema = prefix_items[i]
            if isinstance(pi_schema, dict):
                _validate_schema(
                    instance[i],
                    pi_schema,
                    errors,
                    _jp(path, i),
                    _jp(schema_path, f"prefixItems[{i}]"),
                )

    if items_schema is not None:
        start = len(prefix_items) if prefix_items else 0
        if items_schema is False:
            for i in range(start, len(instance)):
                errors.append(
                    SchemaErrorDetail(
                        path=_jp(path, i),
                        schema_path=_jp(schema_path, "items"),
                        validator="items",
                        message=f"Additional item at index {i} is not allowed at '{_jp(path, i)}'",
                    )
                )
        elif isinstance(items_schema, dict):
            for i in range(start, len(instance)):
                _validate_schema(
                    instance[i],
                    items_schema,
                    errors,
                    _jp(path, i),
                    _jp(schema_path, "items"),
                )


def _check_unique_items(
    instance: list[Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    """Check uniqueItems constraint."""
    try:
        seen: set[Any] = set()
        for i, item in enumerate(instance):
            key = (type(item), item)
            if key in seen:
                errors.append(
                    SchemaErrorDetail(
                        path=_jp(path, i),
                        schema_path=_jp(schema_path, "uniqueItems"),
                        validator="uniqueItems",
                        message=f"Duplicate item {item!r} at '{_jp(path, i)}'",
                    )
                )
                break
            seen.add(key)
    except TypeError:
        for i in range(len(instance)):
            for j in range(i + 1, len(instance)):
                if (
                    type(instance[i]) is type(instance[j])
                    and instance[i] == instance[j]
                ):
                    errors.append(
                        SchemaErrorDetail(
                            path=_jp(path, j),
                            schema_path=_jp(schema_path, "uniqueItems"),
                            validator="uniqueItems",
                            message=f"Duplicate item {instance[j]!r} at '{_jp(path, j)}'",
                        )
                    )
                    break
            else:
                continue
            break


def _check_array(
    instance: Any,
    schema: dict[str, Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    if not isinstance(instance, list):
        return

    _check_array_items(instance, schema, errors, path, schema_path)

    if "minItems" in schema and len(instance) < schema["minItems"]:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "minItems"),
                validator="minItems",
                message=f"Array at '{path or '$'}' has {len(instance)} items, minimum is {schema['minItems']}",
            )
        )
    if "maxItems" in schema and len(instance) > schema["maxItems"]:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "maxItems"),
                validator="maxItems",
                message=f"Array at '{path or '$'}' has {len(instance)} items, maximum is {schema['maxItems']}",
            )
        )

    if schema.get("uniqueItems"):
        _check_unique_items(instance, errors, path, schema_path)

    if "contains" in schema and isinstance(schema["contains"], dict):
        contains_schema = schema["contains"]
        found = False
        for item in instance:
            trial: list[SchemaErrorDetail] = []
            _validate_schema(item, contains_schema, trial, "", "")
            if not trial:
                found = True
                break
        if not found:
            errors.append(
                SchemaErrorDetail(
                    path=path or "$",
                    schema_path=_jp(schema_path, "contains"),
                    validator="contains",
                    message=f"No item in array at '{path or '$'}' matches the 'contains' schema",
                )
            )


# -- Composition handlers ----------------------------------------------------


def _check_allof(
    instance: Any,
    schemas: list[Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    for i, sub in enumerate(schemas):
        if isinstance(sub, (dict, bool)):
            _validate_schema(
                instance, sub, errors, path, _jp(schema_path, f"allOf[{i}]")
            )


def _check_anyof(
    instance: Any,
    schemas: list[Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    for sub in schemas:
        if isinstance(sub, (dict, bool)):
            trial: list[SchemaErrorDetail] = []
            _validate_schema(instance, sub, trial, path, "")
            if not trial:
                return
    errors.append(
        SchemaErrorDetail(
            path=path or "$",
            schema_path=_jp(schema_path, "anyOf"),
            validator="anyOf",
            message=f"Value at '{path or '$'}' does not match any schema in 'anyOf'",
        )
    )


def _check_oneof(
    instance: Any,
    schemas: list[Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    match_indices: list[int] = []
    for i, sub in enumerate(schemas):
        if isinstance(sub, (dict, bool)):
            trial: list[SchemaErrorDetail] = []
            _validate_schema(instance, sub, trial, path, "")
            if not trial:
                match_indices.append(i)
    if len(match_indices) == 0:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "oneOf"),
                validator="oneOf",
                message=f"Value at '{path or '$'}' does not match any schema in 'oneOf'",
            )
        )
    elif len(match_indices) > 1:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "oneOf"),
                validator="oneOf",
                message=f"Value at '{path or '$'}' matches more than one schema in 'oneOf' (indices {match_indices})",
            )
        )


def _check_not(
    instance: Any,
    not_schema: dict[str, Any] | bool,
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    trial: list[SchemaErrorDetail] = []
    _validate_schema(instance, not_schema, trial, path, "")
    if not trial:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=_jp(schema_path, "not"),
                validator="not",
                message=f"Value at '{path or '$'}' should not match the schema in 'not'",
            )
        )


def _check_if_then_else(
    instance: Any,
    schema: dict[str, Any],
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    """Handle ``if``/``then``/``else`` conditional keywords."""
    if_schema = schema["if"]
    trial: list[SchemaErrorDetail] = []
    _validate_schema(instance, if_schema, trial, path, "")
    if not trial:
        then_schema = schema.get("then")
        if then_schema is not None:
            _validate_schema(
                instance, then_schema, errors, path, _jp(schema_path, "then")
            )
    else:
        else_schema = schema.get("else")
        if else_schema is not None:
            _validate_schema(
                instance, else_schema, errors, path, _jp(schema_path, "else")
            )


# -- Core dispatcher ---------------------------------------------------------


def _validate_schema(
    instance: Any,
    schema: dict[str, Any] | bool,
    errors: list[SchemaErrorDetail],
    path: str,
    schema_path: str,
) -> None:
    """Validate *instance* against a single schema node, collecting errors."""
    if schema is True or schema == {}:
        return
    if schema is False:
        errors.append(
            SchemaErrorDetail(
                path=path or "$",
                schema_path=schema_path or "$",
                validator="false_schema",
                message=f"Value at '{path or '$'}' is not allowed (schema is false)",
            )
        )
        return
    if not isinstance(schema, dict):
        return

    if "type" in schema:
        _check_type(instance, schema["type"], errors, path, schema_path)
    if "enum" in schema:
        _check_enum(instance, schema["enum"], errors, path, schema_path)
    if "const" in schema:
        _check_const(instance, schema["const"], errors, path, schema_path)
    _check_string(instance, schema, errors, path, schema_path)
    _check_number(instance, schema, errors, path, schema_path)
    _check_object(instance, schema, errors, path, schema_path)
    _check_array(instance, schema, errors, path, schema_path)
    if "allOf" in schema and isinstance(schema["allOf"], list):
        _check_allof(instance, schema["allOf"], errors, path, schema_path)
    if "anyOf" in schema and isinstance(schema["anyOf"], list):
        _check_anyof(instance, schema["anyOf"], errors, path, schema_path)
    if "oneOf" in schema and isinstance(schema["oneOf"], list):
        _check_oneof(instance, schema["oneOf"], errors, path, schema_path)
    if "not" in schema:
        _check_not(instance, schema["not"], errors, path, schema_path)
    if "if" in schema:
        _check_if_then_else(instance, schema, errors, path, schema_path)


# ---------------------------------------------------------------------------
# Phase 6 — Public validation API
# ---------------------------------------------------------------------------


def iter_errors(
    instance: Any,
    schema: dict[str, Any] | bool,
    *,
    resolved: bool = False,
) -> list[SchemaErrorDetail]:
    """Validate *instance* against JSON Schema *schema* and return all errors.

    The schema is preprocessed: ``$ref`` pointers are resolved before
    validation.  Composition keywords (``allOf``, ``anyOf``, ``oneOf``,
    ``not``) are evaluated semantically, not merged.

    When validating many instances against the same schema, resolve once
    and pass ``resolved=True`` to skip redundant ``$ref`` resolution::

        schema = resolve_refs(raw_schema)
        for item in items:
            errors = iter_errors(item, schema, resolved=True)

    Args:
        instance: The data to validate.
        schema: A JSON Schema dict, or a boolean schema.
        resolved: If ``True``, skip ``$ref`` resolution (caller already
            called :func:`resolve_refs`).  Defaults to ``False`` because
            passing an unresolved schema with ``resolved=True`` silently
            skips ``$ref`` targets — the validator would ignore them and
            report no errors for the referenced sub-schemas.

    Returns:
        A list of :class:`SchemaErrorDetail`; empty if valid.
    """
    errors: list[SchemaErrorDetail] = []
    if isinstance(schema, bool):
        _validate_schema(instance, schema, errors, "", "")
        return errors
    effective = schema if resolved else resolve_refs(schema)
    _validate_schema(instance, effective, errors, "", "")
    return errors


def schema_validate(
    instance: Any,
    schema: dict[str, Any] | bool,
    *,
    resolved: bool = False,
) -> None:
    """Validate *instance* against JSON Schema *schema*.

    Args:
        instance: The data to validate.
        schema: A JSON Schema dict.
        resolved: If ``True``, skip ``$ref`` resolution (caller already
            called :func:`resolve_refs`).  Must not be set to ``True``
            unless the schema has been resolved — unresolved ``$ref``
            nodes would be silently ignored.

    Raises:
        SchemaValidationError: If validation fails, with all errors collected.
    """
    errors = iter_errors(instance, schema, resolved=resolved)
    if errors:
        raise SchemaValidationError(errors)
