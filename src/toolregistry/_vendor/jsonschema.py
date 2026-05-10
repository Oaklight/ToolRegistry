# /// zerodep
# version = "0.2.0"
# deps = []
# tier = "medium"
# category = "validation"
# note = "Install/update via `zerodep add jsonschema`"
# ///
"""JSON Schema flattening & sanitization — zero dependencies, stdlib only.

Flatten complex JSON Schemas containing ``$ref``, ``allOf``, ``anyOf``, and
``oneOf`` into simple, LLM-provider-compatible schemas.  Designed for tool
schemas consumed by Anthropic, OpenAI, and Google GenAI APIs.

Part of zerodep: https://github.com/Oaklight/zerodep
Copyright (c) 2026 Peng Ding. MIT License.

Example::

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

Pipeline::

    resolve_refs  →  merge_allof  →  simplify_unions  →  sanitize
"""

from __future__ import annotations

import copy
import warnings
from typing import Any

__all__ = [
    "flatten_schema",
    "resolve_refs",
    "merge_allof",
    "simplify_unions",
    "sanitize",
    "UNSUPPORTED_SCHEMA_KEYS",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFS_KEYS: set[str] = {"$defs", "definitions"}

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


def _walk_merge_allof(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge all ``allOf`` nodes in *schema*."""
    # First recurse into children so nested allOf are resolved bottom-up.
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            result[key] = _walk_merge_allof(value)
        elif isinstance(value, list):
            result[key] = [
                _walk_merge_allof(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    if "allOf" in result and isinstance(result["allOf"], list):
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
            # Lossy but safe for LLM tool schemas: keep first non-null variant.
            base = _deep_merge_two(base, non_null[0])
        # else: all null — base stays as-is

        if has_null:
            base["nullable"] = True

        return base

    return schema


def _walk_simplify(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively simplify all ``anyOf``/``oneOf`` nodes."""
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            result[key] = _walk_simplify(value)
        elif isinstance(value, list):
            result[key] = [
                _walk_simplify(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    if result.keys() & {"anyOf", "oneOf"}:
        result = _simplify_node(result)
    return result


def simplify_unions(schema: dict[str, Any]) -> dict[str, Any]:
    """Simplify ``anyOf``/``oneOf`` constructs.

    - Nullable pattern ``[{type: T}, {type: null}]`` → ``{type: T, nullable: true}``
    - Single-variant: unwrap.
    - Multi-variant: keep first non-null variant (lossy but safe for LLM tool
      schemas).

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
) -> dict[str, Any]:
    """Recursively strip unsupported keys and prune orphaned ``required``."""
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key in strip:
            continue
        if isinstance(value, dict):
            result[key] = _walk_sanitize(value, strip)
        elif isinstance(value, list):
            result[key] = [
                _walk_sanitize(item, strip) if isinstance(item, dict) else item
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
