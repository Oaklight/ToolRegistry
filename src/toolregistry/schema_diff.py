"""Classify JSON Schema changes as compatible or breaking.

This module provides lightweight heuristics for determining whether a
change to a tool's parameter schema is backward-compatible (safe for
existing callers) or breaking (likely to cause call failures).

Known limitations:

- Only inspects top-level properties.  Nested object changes (e.g. a
  property of type ``object`` whose sub-properties change) are not
  detected.
- All type changes are treated as breaking.  Type widenings (e.g.
  ``integer`` → ``number``) are not yet recognized as compatible.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any


class SchemaChangeKind(str, Enum):
    """Classification of a schema change's backward-compatibility impact.

    Attributes:
        COMPATIBLE: Additive-only change — new optional parameters,
            description updates, relaxed requirements.  Existing callers
            are unaffected.
        BREAKING: Destructive change — removed parameters, new required
            parameters, type changes.  Existing callers may fail.
        UNKNOWN: Cannot determine compatibility — e.g. complete schema
            replacement with no structural overlap.
    """

    COMPATIBLE = "compatible"
    BREAKING = "breaking"
    UNKNOWN = "unknown"


def classify_schema_change(
    old: dict[str, Any],
    new: dict[str, Any],
) -> tuple[SchemaChangeKind, dict[str, Any]]:
    """Classify a schema change and produce a diff summary.

    Args:
        old: The previous JSON Schema dict.
        new: The updated JSON Schema dict.

    Returns:
        A ``(kind, summary)`` tuple where *kind* is the compatibility
        classification and *summary* is a dict describing what changed::

            {
                "added_optional": ["param_c"],
                "added_required": ["param_d"],
                "removed": ["param_a"],
                "newly_required": ["param_b"],
                "no_longer_required": ["param_e"],
                "type_changed": {"param_x": {"old": "string", "new": "integer"}},
            }

        Empty lists/dicts are omitted from the summary.
    """
    old_props = old.get("properties", {})
    new_props = new.get("properties", {})
    old_required = set(old.get("required", []))
    new_required = set(new.get("required", []))

    old_keys = set(old_props.keys())
    new_keys = set(new_props.keys())

    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys
    common_keys = old_keys & new_keys

    # No structural overlap — can't determine compatibility
    if not old_keys and not new_keys:
        return SchemaChangeKind.COMPATIBLE, {}
    if old_keys and new_keys and not common_keys:
        return SchemaChangeKind.UNKNOWN, {
            "added": sorted(new_keys),
            "removed": sorted(old_keys),
        }

    added_required = [k for k in sorted(added_keys) if k in new_required]
    added_optional = [k for k in sorted(added_keys) if k not in new_required]
    removed = sorted(removed_keys)

    newly_required = sorted(
        k for k in common_keys if k not in old_required and k in new_required
    )
    no_longer_required = sorted(
        k for k in common_keys if k in old_required and k not in new_required
    )

    type_changed: dict[str, dict[str, Any]] = {}
    for k in sorted(common_keys):
        old_type = _extract_type(old_props[k])
        new_type = _extract_type(new_props[k])
        if old_type != new_type:
            type_changed[k] = {"old": old_type, "new": new_type}

    summary: dict[str, Any] = {}
    if added_optional:
        summary["added_optional"] = added_optional
    if added_required:
        summary["added_required"] = added_required
    if removed:
        summary["removed"] = removed
    if newly_required:
        summary["newly_required"] = newly_required
    if no_longer_required:
        summary["no_longer_required"] = no_longer_required
    if type_changed:
        summary["type_changed"] = type_changed

    is_breaking = bool(added_required or removed or newly_required or type_changed)
    kind = SchemaChangeKind.BREAKING if is_breaking else SchemaChangeKind.COMPATIBLE

    return kind, summary


def _extract_type(prop_schema: dict[str, Any]) -> Any:
    """Extract a comparable type representation from a property schema."""
    if "type" in prop_schema:
        return prop_schema["type"]
    if "anyOf" in prop_schema:
        types = tuple(
            sorted(json.dumps(s, sort_keys=True) for s in prop_schema["anyOf"])
        )
        return ("anyOf", types)
    if "oneOf" in prop_schema:
        types = tuple(
            sorted(json.dumps(s, sort_keys=True) for s in prop_schema["oneOf"])
        )
        return ("oneOf", types)
    if "allOf" in prop_schema:
        types = tuple(
            sorted(json.dumps(s, sort_keys=True) for s in prop_schema["allOf"])
        )
        return ("allOf", types)
    return None


def classify_tool_change(
    old_hash: str,
    new_hash: str,
    old_params: dict[str, Any],
    new_params: dict[str, Any],
) -> tuple[SchemaChangeKind, dict[str, Any]]:
    """Classify a tool update, distinguishing schema changes from description-only.

    Args:
        old_hash: Schema hash of the existing tool.
        new_hash: Schema hash of the candidate tool.
        old_params: Parameter schema of the existing tool.
        new_params: Parameter schema of the candidate tool.

    Returns:
        A ``(kind, summary)`` tuple.  When hashes match (description-only
        change), returns ``(COMPATIBLE, {"description_only": True})``.
    """
    if old_hash != new_hash:
        return classify_schema_change(old_params, new_params)
    return SchemaChangeKind.COMPATIBLE, {"description_only": True}
