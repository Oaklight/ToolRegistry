"""Namespace mixin for ToolRegistry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from .._names import (
    NameSeparator,
    is_in_namespace,
    namespace_prefix,
)
from ..tool import Tool
from ..utils import normalize_tool_name


def _rekey_tool(tool: Tool, sep: NameSeparator) -> Tool:
    """Return *tool* re-keyed with *sep*, preserving its namespace."""
    return tool.requalify(tool.namespace, sep) if tool.namespace else tool


class NamespaceMixin:
    """Mixin providing namespace management, tool lookup, merge, and spinoff."""

    name: str
    _overrides: dict[str, Tool]  # Owned by RegistrationMixin
    _disabled: dict[str, str]  # Owned by EnableDisableMixin
    _execution_mode: str  # Owned by ToolRegistry
    name_sep: NameSeparator  # Property exposed by ToolRegistry

    if TYPE_CHECKING:

        def get_disable_reason(self, tool_name: str) -> str | None: ...

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tools: dict[str, Tool] = {}
        self._sub_registries: set[str] = set()

    def _update_sub_registries(self) -> None:
        """Update the internal set of sub-registries based on the registered tools.

        This method identifies sub-registry prefixes by examining the ``namespace``
        field of each tool first.  If a tool does not have a ``namespace`` set, it
        falls back to parsing the tool name with the registry's ``name_sep``.

        Side Effects:
            Modifies the `_sub_registries` attribute with the latest prefixes.

        Returns:
            None
        """
        prefixes: set[str] = set()
        for tool in self._tools.values():
            prefix = tool.namespace or namespace_prefix(tool.name, self.name_sep)
            if prefix:
                prefixes.add(prefix)
        self._sub_registries = prefixes

    def _sync_overrides(self, remap: Callable[[str, Tool], tuple[str, Tool]]) -> None:
        """Rebuild ``_overrides`` after the ``_tools`` keys change.

        ``_overrides`` (owned by :class:`RegistrationMixin`) is keyed by
        registered tool name, so every helper that renames or moves tools must
        keep it in sync.  Names that were renamed are remapped; records whose
        new name is no longer registered are dropped as stranded.

        Args:
            remap: Maps an ``(old_name, displaced_tool)`` pair to its new
                ``(name, tool)``.
        """
        overrides = getattr(self, "_overrides", None)
        if not overrides:
            return
        rebuilt: dict[str, Tool] = {}
        for name, displaced in overrides.items():
            new_name, new_tool = remap(name, displaced)
            if new_name in self._tools:
                rebuilt[new_name] = new_tool
        self._overrides = rebuilt

    def _rekey_disabled(self, remap: dict[str, str]) -> None:
        """Move disabled records to the tools' new names.

        ``_disabled`` (owned by :class:`EnableDisableMixin`) is keyed by name.
        Method-level entries follow their tool through *remap*; namespace-level
        entries are left alone because namespaces do not carry the registry
        separator.

        Args:
            remap: Maps old tool names to their new names.
        """
        disabled = getattr(self, "_disabled", None)
        if not disabled:
            return
        self._disabled = {
            remap.get(name, name): reason for name, reason in disabled.items()
        }

    def _prefix_tools_namespace(self, force: bool = False) -> None:
        """Add the registry name as a prefix to the names of tools in the registry.

        This method updates the names of tools in the `_tools` dictionary by prefixing
        them with the registry's name if they don't already have a prefix. Tools that
        already have a prefix retain their existing name.

        Args:
            force (bool): If True, forces the namespace update for all tools, even if they already have a prefix.
                If False, retains existing prefixes for tools that already have one.

        Side Effects:
            Updates the `_tools` dictionary with potentially modified tool names.
            Re-keys `_overrides` alongside it.

        Example:
            With the default ``name_sep="-"`` and a registry named
            ``main_registry``:
            - A tool named ``tool_a`` becomes ``main_registry-tool_a``.
            - A tool already in ``other_registry`` keeps its name when
              ``force=False``.
            - With ``force=True`` every tool is rebuilt under
              ``main_registry`` using the registry separator.

        Raises:
            None
        """
        sep = self.name_sep
        # Snapshot each tool's effective disabled state (method-level over
        # namespace-level) before renaming, so it can follow the tool.
        disabled_reasons = {name: self.get_disable_reason(name) for name in self._tools}
        new_tools: dict[str, Tool] = {}
        rename: dict[str, str] = {}
        for old_name, tool in self._tools.items():
            updated = tool.update_namespace(self.name, force=force, sep=sep)
            new_tools[updated.name] = updated
            rename[old_name] = updated.name
        self._tools = new_tools
        self._sync_overrides(
            lambda name, displaced: (
                rename.get(name, name),
                displaced.update_namespace(self.name, force=force, sep=sep),
            )
        )
        if getattr(self, "_disabled", None) is not None:
            for old_name in disabled_reasons:
                self._disabled.pop(old_name, None)
            for old_name, new_name in rename.items():
                reason = disabled_reasons.get(old_name)
                if reason is not None:
                    self._disabled[new_name] = reason

    def _convert_incoming(
        self, other: NamespaceMixin, sep: NameSeparator
    ) -> tuple[dict[str, Tool], dict[str, str]]:
        """Re-key *other*'s tools with *sep*; return tools and the name remap."""
        incoming: dict[str, Tool] = {}
        remap: dict[str, str] = {}
        for name, tool in other._tools.items():
            converted = _rekey_tool(tool, sep)
            if converted.name in incoming:
                raise ValueError(
                    f"Merge would collapse {name!r} and another tool into "
                    f"{converted.name!r}; rename one of them first."
                )
            incoming[converted.name] = converted
            remap[name] = converted.name
        return incoming, remap

    def _apply_incoming(
        self, incoming: dict[str, Tool], keep_existing: bool
    ) -> set[str]:
        """Merge *incoming* into ``_tools`` and return the names that came over."""
        if keep_existing:
            merged: set[str] = set()
            for name, tool in incoming.items():
                if name not in self._tools:
                    self._tools[name] = tool
                    merged.add(name)
            return merged

        self._tools.update(incoming)
        # Incoming tools supersede any override holding the same name, so the
        # displaced record no longer describes the current tool.
        for name in incoming:
            self._overrides.pop(name, None)
        return set(incoming)

    def _carry_overrides(
        self,
        other: NamespaceMixin,
        remap: dict[str, str],
        merged_keys: set[str],
        sep: NameSeparator,
    ) -> None:
        """Move override records for tools that actually came over."""
        for old_name, displaced in other._overrides.items():
            new_name = remap.get(old_name)
            if new_name is None or new_name not in merged_keys:
                continue
            self._overrides[new_name] = _rekey_tool(displaced, sep)

    def _carry_disabled(
        self,
        other: NamespaceMixin,
        remap: dict[str, str],
        merged_keys: set[str],
    ) -> None:
        """Move disabled state for tools that actually came over."""
        if getattr(self, "_disabled", None) is None:
            return
        for old_name, new_name in remap.items():
            if new_name not in merged_keys:
                continue
            reason = other.get_disable_reason(old_name)
            if reason is not None:
                self._disabled[new_name] = reason

    def merge(
        self,
        other: NamespaceMixin,
        keep_existing: bool = False,
        force_namespace: bool = False,
    ):
        """Merge tools from another ToolRegistry into this one.

        This method directly updates the current registry with tools from another
        registry, avoiding the need to create a new ToolRegistry object.

        Args:
            other (ToolRegistry): The ToolRegistry to merge from.
            keep_existing (bool): If True, preserves existing tools on name conflicts.
            force_namespace (bool): If True, forces updating tool namespaces by prefixing them with the registry name; if False, retains existing namespaces.

        Raises:
            TypeError: If other is not a ToolRegistry instance.
        """
        from ..tool_registry import ToolRegistry

        if not isinstance(other, ToolRegistry):
            raise TypeError("Can only merge with another ToolRegistry instance.")

        sep = self.name_sep

        # Prefix tools in both registries.  ``force=False`` leaves tools that
        # already carry a namespace untouched, so their name and namespace stay
        # consistent.
        self._prefix_tools_namespace()
        other._prefix_tools_namespace()

        incoming, remap = self._convert_incoming(other, sep)
        merged_keys = self._apply_incoming(incoming, keep_existing)
        self._carry_overrides(other, remap, merged_keys, sep)
        self._carry_disabled(other, remap, merged_keys)

        if force_namespace:
            # update namespace if required after merge done
            self._prefix_tools_namespace(force=force_namespace)

        # Update sub-registries based on merged tools
        self._update_sub_registries()

    def reduce_namespace(self) -> None:
        """Remove the namespace from tools in the registry if there is only one sub-registry.

        This method checks if there is only one sub-registry remaining in the registry.
        If so, every tool in that namespace is flattened by rebuilding its name from
        ``method_name``.  Tools without a namespace, or in a different namespace, are
        left untouched.

        Raises:
            ValueError: If flattening would make two tools collide.

        Side Effects:
            - Updates the `_tools` dictionary and each flattened ``Tool.name``.
            - Re-keys `_overrides` alongside the tools.
            - Clears the `_sub_registries` set if namespace flattening occurs.

        Example:
            If the registry contains tools with names like ``calculator-add`` and
            ``calculator-subtract``, and ``calculator`` is the only sub-registry,
            this method renames them to ``add`` and ``subtract``.
        """
        if len(self._sub_registries) != 1:
            return

        remaining_prefix = next(iter(self._sub_registries))
        sep = self.name_sep

        def flatten(name: str, tool: Tool) -> tuple[str, Tool]:
            if tool.namespace:
                if tool.namespace != remaining_prefix:
                    return name, tool
            elif not is_in_namespace(name, remaining_prefix, sep):
                return name, tool
            flat = tool.requalify(None, sep)
            return flat.name, flat

        reduced: dict[str, Tool] = {}
        remap: dict[str, str] = {}
        disabled_reasons: dict[str, str] = {}
        for name, tool in self._tools.items():
            new_name, new_tool = flatten(name, tool)
            if new_name in reduced:
                raise ValueError(
                    f"Cannot reduce namespace {remaining_prefix!r}: "
                    f"{name!r} would collide with an existing tool at "
                    f"{new_name!r}."
                )
            reduced[new_name] = new_tool
            remap[name] = new_name
            reason = self.get_disable_reason(name)
            if reason is not None:
                disabled_reasons[new_name] = reason

        self._tools = reduced
        self._sync_overrides(flatten)
        if getattr(self, "_disabled", None) is not None:
            for old_name in remap:
                self._disabled.pop(old_name, None)
            self._disabled.pop(remaining_prefix, None)
            self._disabled.update(disabled_reasons)
        self._sub_registries.clear()

    def _select_namespace_tools(
        self, prefix: str, sep: NameSeparator
    ) -> tuple[dict[str, Tool], set[str], dict[str, str]]:
        """Select tools in *prefix*.

        Returns the selected tools keyed by their (possibly requalified) name,
        the source keys, and a source-key → child-key map.
        """
        tools: dict[str, Tool] = {}
        selected_keys: set[str] = set()
        source_to_child: dict[str, str] = {}
        for name, tool in self._tools.items():
            if tool.namespace:
                matches = tool.namespace == prefix
            else:
                matches = is_in_namespace(name, prefix, sep)
            if not matches:
                continue

            # Give legacy (namespace-less) tools their group marker before
            # moving them, so later operations never have to parse their names.
            if not tool.namespace:
                tool = tool.requalify(prefix, sep)
            tools[tool.name] = tool
            selected_keys.add(name)
            source_to_child[name] = tool.name
        return tools, selected_keys, source_to_child

    def _drop_moved_disabled(self, selected_keys: set[str], prefix: str) -> None:
        """Drop disabled records for tools that left this registry."""
        if getattr(self, "_disabled", None) is None:
            return
        for name in selected_keys:
            self._disabled.pop(name, None)
        if not any(tool.namespace == prefix for tool in self._tools.values()):
            self._disabled.pop(prefix, None)

    def spinoff(self, prefix: str, retain_namespace: bool = False) -> NamespaceMixin:
        """Spin off tools with the specified namespace into a new registry.

        Tools are selected by their ``namespace`` field (the authoritative group
        marker); a key-prefix match is used only for legacy tools that were added
        without one.  Matching uses the registry's ``name_sep`` and the prefix is
        normalized first, so ``"MyMath"`` finds tools in ``my_math``.

        Args:
            prefix (str): Namespace to spin off.
            retain_namespace (bool): If True, keeps qualified names in the
                spun-off registry and skips namespace reduction in both
                registries.  If False, flattens the spun-off tools and calls
                :meth:`reduce_namespace` on the source when only one namespace
                remains.

        Returns:
            ToolRegistry: A new registry containing the spun-off tools.  It
            inherits this registry's ``name_sep``.

        Raises:
            ValueError: If no tools in the specified namespace are found.

        Notes:
            When `retain_namespace` is False, the `reduce_namespace` method is
            called to remove the namespace from tools in the current registry.
        """
        from ..tool_registry import ToolRegistry

        normalized_prefix = normalize_tool_name(prefix)
        sep = self.name_sep

        spun_off_tools, selected_keys, source_to_child = self._select_namespace_tools(
            normalized_prefix, sep
        )

        if not spun_off_tools:
            raise ValueError(f"No tools with prefix '{prefix}' found in the registry.")

        # Capture effective disabled state before the move so it can follow the
        # tools into the child registry.
        disabled_reasons = {
            source_to_child[name]: self.get_disable_reason(name)
            for name in selected_keys
        }

        # Create a new registry for the spun-off tools, inheriting the separator
        # and execution mode.
        new_registry = ToolRegistry(name=normalized_prefix, name_sep=sep)
        new_registry._execution_mode = self._execution_mode
        new_registry._sub_registries.add(normalized_prefix)
        new_registry._tools = spun_off_tools
        for new_name, reason in disabled_reasons.items():
            if reason is not None:
                new_registry._disabled[new_name] = reason

        moved_overrides = {
            name: displaced
            for name, displaced in self._overrides.items()
            if name in selected_keys
        }
        if moved_overrides:
            # Override records follow the tools they belong to.
            new_registry._overrides = moved_overrides
            for name in moved_overrides:
                self._overrides.pop(name, None)

        if not retain_namespace:
            new_registry.reduce_namespace()

        # Remove the spun-off tools from the current registry
        self._tools = {
            name: tool
            for name, tool in self._tools.items()
            if name not in selected_keys
        }

        # Remove the prefix from sub-registries if it exists
        self._sub_registries.discard(normalized_prefix)

        # The moved tools no longer belong to this registry; drop their
        # method-level disabled records, and the namespace-level record once no
        # tool in that namespace remains.
        self._drop_moved_disabled(selected_keys, normalized_prefix)

        # Optionally discard namespace if retain_namespace is False
        if not retain_namespace:
            self.reduce_namespace()

        return new_registry

    def get_tool(self, tool_name: str) -> Tool | None:
        """Get a tool by its name.

        Args:
            tool_name (str): Name of the tool to retrieve.

        Returns:
            Optional[Tool]: The tool, or None if not found.
        """
        tool = self._tools.get(tool_name)
        return tool

    def get_callable(self, tool_name: str) -> Callable[..., Any] | None:
        """Get a callable function by its name.

        Args:
            tool_name (str): Name of the function to retrieve.

        Returns:
            Optional[Callable[..., Any]]: The function to call, or None if not found.
        """
        tool = self.get_tool(tool_name)
        return tool.callable if tool else None
