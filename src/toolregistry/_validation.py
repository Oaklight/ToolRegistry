"""Shared validation for ``ToolMetadata`` field values.

Both the runtime metadata update paths
(:meth:`ToolRegistry.update_tool_metadata` and
:meth:`ToolRegistry.update_namespace_metadata`) and the config loader accept
the same execution-hint fields, so the accepted types are defined here once.
The loader translates :class:`MetadataFieldTypeError` into a path-qualified
``ConfigError``; the runtime paths let it propagate as a ``ValueError``.
"""

from __future__ import annotations

from typing import Any

#: Optional boolean metadata fields; ``None`` means "unset".
OPTIONAL_BOOL_FIELDS: frozenset[str] = frozenset(
    {
        "read_only_hint",
        "destructive_hint",
        "idempotent_hint",
        "open_world_hint",
    }
)

#: Optional string metadata fields; ``None`` means "unset".
OPTIONAL_STR_FIELDS: frozenset[str] = frozenset({"title"})

#: Execution-hint metadata fields validated on the runtime update paths.
HINT_METADATA_FIELDS: frozenset[str] = OPTIONAL_BOOL_FIELDS | OPTIONAL_STR_FIELDS


class MetadataFieldTypeError(ValueError):
    """A metadata field value has the wrong type.

    Attributes:
        field: Name of the offending metadata field.
        expected: Human-readable description of the accepted type, for
            example ``"a boolean"``.
    """

    def __init__(self, field: str, expected: str) -> None:
        self.field = field
        self.expected = expected
        super().__init__(f"Field '{field}' must be {expected}.")


def ensure_optional_bool(field: str, value: Any) -> None:
    """Check that *value* is ``None`` or a ``bool``.

    Args:
        field: Field name, used in the error message.
        value: Candidate value.

    Raises:
        MetadataFieldTypeError: If *value* is neither ``None`` nor a bool.
    """
    if value is not None and not isinstance(value, bool):
        raise MetadataFieldTypeError(field, "a boolean")


def ensure_optional_string(field: str, value: Any) -> None:
    """Check that *value* is ``None`` or a ``str``.

    Args:
        field: Field name, used in the error message.
        value: Candidate value.

    Raises:
        MetadataFieldTypeError: If *value* is neither ``None`` nor a str.
    """
    if value is not None and not isinstance(value, str):
        raise MetadataFieldTypeError(field, "a string")


def validate_metadata_field(field: str, value: Any) -> None:
    """Validate one execution-hint metadata field against its accepted type.

    Fields outside ``HINT_METADATA_FIELDS`` pass through unchecked so this
    helper stays additive to the pre-existing mutable fields.

    Args:
        field: Metadata field name.
        value: Candidate value; ``None`` is always accepted.

    Raises:
        MetadataFieldTypeError: If *field* is a known hint field and *value*
            has the wrong type.
    """
    if field in OPTIONAL_BOOL_FIELDS:
        ensure_optional_bool(field, value)
    elif field in OPTIONAL_STR_FIELDS:
        ensure_optional_string(field, value)
