"""Single source of truth for tool names.

Every registration path — native functions, class methods, and remote
integrations — must agree on the key a tool is stored under.  Keeping the
rules in one place is what lets the integrations filter on the final name
before constructing a tool, and lets refresh diff against the names that
were actually registered.

The module also owns name normalization and the include/exclude filter used
while registering remote tools.  :mod:`toolregistry.utils` re-exports these
names for compatibility.
"""

from __future__ import annotations

import fnmatch
import re
from typing import Literal

from ._warnings import warn_at_user_frame

__all__ = [
    "NameSeparator",
    "ToolNameFilter",
    "is_in_namespace",
    "namespace_prefix",
    "normalize_tool_name",
    "qualify_name",
    "qualified_tool_name",
    "strip_namespace",
]

NameSeparator = Literal["-", "."]


def qualify_name(
    name: str,
    namespace: str,
    sep: NameSeparator = "-",
    *,
    force: bool = True,
    method_name: str | None = None,
) -> tuple[str, str]:
    """Apply *namespace* to an already-normalized *name*.

    ``force=True`` replaces an existing namespace prefix (the prefix is
    everything before the first *sep*).  ``force=False`` keeps the name
    unchanged when it already carries a prefix.  The method name is derived
    from the name when not supplied.

    Args:
        name: Normalized tool name, with or without a namespace prefix.
        namespace: Namespace to apply.  Normalized before use.
        sep: Separator between namespace and method name.
        force: Whether to replace an existing prefix.
        method_name: Known method name, if any.

    Returns:
        ``(qualified_name, method_name)``.
    """
    normalized_ns = normalize_tool_name(namespace)
    if not method_name:
        method_name = name.split(sep, 1)[1] if sep in name else name

    if sep in name:
        qualified = f"{normalized_ns}{sep}{name.split(sep, 1)[1]}" if force else name
    else:
        qualified = f"{normalized_ns}{sep}{name}"

    return qualified, method_name


def qualified_tool_name(
    raw_name: str,
    namespace: str | None,
    sep: NameSeparator = "-",
) -> str:
    """Return the registry key a tool will be stored under.

    This mirrors what :meth:`ToolRegistry._register_native` does with
    ``namespace`` and the registry separator, without constructing a tool.
    Integrations use it to filter on the final name before building a
    wrapper, and to keep registration and refresh in agreement.

    Args:
        raw_name: Name advertised by the source or passed by the caller.
        namespace: Namespace to apply, or ``None``/empty for none.
        sep: Registry separator.

    Returns:
        The normalized, namespace-qualified name.
    """
    normalized = normalize_tool_name(raw_name)
    if not namespace:
        return normalized
    qualified, _ = qualify_name(normalized, namespace, sep, force=True)
    return qualified


def namespace_prefix(name: str, sep: NameSeparator = "-") -> str | None:
    """Return the namespace part of a qualified *name*, or ``None``.

    Names created by ToolRegistry are normalized, so a separator in a key is
    always the namespace boundary.  The caller supplies the registry separator.

    Args:
        name: Tool name, possibly namespace-qualified.
        sep: Registry separator.

    Returns:
        The prefix before the first *sep*, or ``None`` when *name* is
        unqualified.
    """
    if sep not in name:
        return None
    return name.split(sep, 1)[0]


def is_in_namespace(name: str, namespace: str, sep: NameSeparator = "-") -> bool:
    """Whether *name* belongs to *namespace* under *sep*.

    The prefix must end on a separator boundary, so ``math`` matches
    ``math-add`` but not ``math_ops-add``.  *namespace* must already be
    normalized.

    Args:
        name: Tool name to test.
        namespace: Normalized namespace to match.
        sep: Registry separator.

    Returns:
        ``True`` when *name* carries ``namespace + sep``.
    """
    return bool(namespace) and name.startswith(f"{namespace}{sep}")


def strip_namespace(name: str, namespace: str, sep: NameSeparator = "-") -> str:
    """Remove a leading ``namespace + sep`` from *name*.

    Returns *name* unchanged when it does not belong to *namespace*, so callers
    never blind-slice a name that is merely shorter or in another namespace.

    Args:
        name: Tool name, possibly namespace-qualified.
        namespace: Normalized namespace to remove.
        sep: Registry separator.

    Returns:
        The unqualified name, or *name* unchanged.
    """
    if not is_in_namespace(name, namespace, sep):
        return name
    return name[len(namespace) + len(sep) :]


def normalize_tool_name(name: str) -> str:
    """Normalize tool name to snake_case format and remove dots and spaces.
    Also handles OpenAPI-style duplicate names like 'add_add_get' by converting to 'add_get'.

    Args:
        name: Original tool name in various formats (including CamelCase, UpperCamelCase, or containing spaces)

    Returns:
        str: Normalized name in snake_case without dots or spaces
    """
    # First check for OpenAPI-style duplicate names (e.g. "add_add_get")
    openapi_pattern = r"^([a-zA-Z0-9]+)_\1_([a-zA-Z0-9]+)$"
    match = re.match(openapi_pattern, name)
    if match:
        return f"{match.group(1)}_{match.group(2)}"

    # Replace all special chars (., -, @, etc.) with single underscore
    name = re.sub(r"[.\-@]+", "_", name)

    # Remove spaces and collapse multiple spaces into a single space
    name = re.sub(r"\s+", " ", name).strip()

    # Replace spaces with underscores
    name = name.replace(" ", "_")

    # Convert CamelCase and UpperCamelCase to snake_case
    # Handles all cases including:
    # XMLParser -> xml_parser
    # getUserIDFromDB -> get_user_id_from_db
    # HTTPRequest -> http_request
    name = re.sub(r"(?<!^)(?=[A-Z][a-z])|(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()

    # Collapse multiple underscores into single underscore
    return re.sub(r"_+", "_", name)


def _as_pattern_list(value: str | list[str] | None) -> list[str] | None:
    """Normalize an ``include`` / ``exclude`` argument to a pattern list.

    A bare string is a single pattern, not an iterable of characters.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


def _name_spellings(raw_name: str, namespaced_name: str) -> tuple[str, ...]:
    """Return the name spellings a filter pattern may match.

    The source-advertised name and the registered name are matched as-is,
    plus their snake_case normalizations.  Order is preserved and
    duplicates are dropped.
    """
    spellings = (
        raw_name,
        namespaced_name,
        normalize_tool_name(raw_name),
        normalize_tool_name(namespaced_name),
    )
    return tuple(dict.fromkeys(spellings))


class ToolNameFilter:
    """Include/exclude filter applied when registering remote tools.

    Patterns are matched with :func:`fnmatch.fnmatchcase` against four
    spellings of each candidate name: the raw remote tool name (the name
    the source advertises, e.g. the MCP tool name or the OpenAPI
    ``operationId``), the final post-namespace name (e.g.
    ``gh-list_issues``), and the :func:`normalize_tool_name` form of each.
    A pattern therefore matches a tool when it matches any spelling, so
    ``bash-execute``, ``bash_execute``, ``hub-bash_execute``, and
    ``hub_bash_execute`` all select the same tool.

    ``include`` and ``exclude`` are mutually exclusive.  ``None`` means the
    corresponding side is not filtered; an empty list matches nothing, so
    ``include=[]`` drops every tool.  A bare string is treated as a
    single-pattern list, so a one-item JSON/YAML ``include: name`` is not
    mistaken for an iterable of characters.

    Matching is case-sensitive (:func:`fnmatch.fnmatchcase`), unlike
    ``discover_tools`` / ``call_deferred``, which fold case.  Write
    patterns in the case the source advertises.

    The normalized spelling is not unique.  When a source advertises two
    names that normalize to the same string (for example ``x-y`` and
    ``x_y``), a pattern written in that spelling selects both tools.  Use
    the raw or post-namespace spelling to narrow to one of them.

    Args:
        include: Names or glob patterns to keep.  When given, a tool is
            kept only if one of its spellings matches a pattern.
        exclude: Names or glob patterns to drop.  When given, a tool is
            dropped if one of its spellings matches a pattern.

    Raises:
        ValueError: If both ``include`` and ``exclude`` are given.
    """

    def __init__(
        self,
        include: str | list[str] | None = None,
        exclude: str | list[str] | None = None,
    ) -> None:
        if include is not None and exclude is not None:
            raise ValueError(
                "include and exclude are mutually exclusive; pass only one."
            )
        self.include = _as_pattern_list(include)
        self.exclude = _as_pattern_list(exclude)

    def accepts(self, raw_name: str, namespaced_name: str) -> bool:
        """Return whether a tool passes the filter.

        Args:
            raw_name: The remote tool name before namespace handling.
            namespaced_name: The final registered name (``raw_name`` plus
                any namespace prefix).

        Returns:
            True if the tool should be registered, False if it must be
            dropped.
        """
        candidates = _name_spellings(raw_name, namespaced_name)
        if self.include is not None:
            return any(
                fnmatch.fnmatchcase(name, pattern)
                for pattern in self.include
                for name in candidates
            )
        if self.exclude is not None:
            return not any(
                fnmatch.fnmatchcase(name, pattern)
                for pattern in self.exclude
                for name in candidates
            )
        return True

    def warn_if_all_filtered_out(
        self,
        *,
        total: int,
        accepted: int,
        source: str,
    ) -> None:
        """Warn when an active filter leaves none of *total* candidates.

        A filter that leaves nothing registered is almost always a
        configuration mistake: an empty list, a bare string, or a pattern
        spelled differently from the names the source advertises.  Without
        this warning registration succeeds and silently produces an empty
        source.

        Args:
            total: Number of candidate tools the source offered.
            accepted: Number of candidates that passed this filter.
            source: Source label used in the message, e.g. ``"MCP"``.

        Warns:
            UserWarning: If a filter is active, *total* is non-zero, and
                *accepted* is zero.
        """
        if self.include is None and self.exclude is None:
            return
        if total <= 0 or accepted > 0:
            return
        if self.include is not None:
            detail = f"include={self.include!r} matched none of {total} tool(s)"
        else:
            detail = f"exclude={self.exclude!r} excluded all {total} tool(s)"
        # Attribute the warning to the caller rather than the integration
        # internals; a fixed stacklevel cannot follow the async bridge.
        warn_at_user_frame(
            f"{source} registration filter {detail}; nothing was registered.",
            UserWarning,
        )
