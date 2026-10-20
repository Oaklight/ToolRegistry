"""Single source of truth for namespace-qualified tool names.

Every registration path — native functions, class methods, and remote
integrations — must agree on the key a tool is stored under.  Keeping the
rule in one place is what lets the integrations filter on the final name
before constructing a tool, and lets refresh diff against the names that
were actually registered.
"""

from __future__ import annotations

from typing import Literal

from .utils import normalize_tool_name

__all__ = ["NameSeparator", "qualify_name", "qualified_tool_name"]

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
