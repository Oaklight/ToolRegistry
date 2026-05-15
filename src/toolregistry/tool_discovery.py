"""Natural language tool discovery using BM25 sparse index.

Provides :class:`ToolDiscoveryTool` which indexes all tools in a
:class:`~toolregistry.ToolRegistry` and exposes a
:meth:`~ToolDiscoveryTool.discover` method that LLMs can call to find
relevant tools by exact name or natural language query.

The search backend is a vendored copy of *zerodep*'s ``SparseIndex``
(BM25/BM25F scoring, zero external dependencies).
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

from ._vendor.sparse_search import SparseIndex

if TYPE_CHECKING:
    from .tool import Tool
    from .tool_registry import ToolRegistry
    from .types import API_FORMATS

_DEFAULT_FIELD_WEIGHTS: dict[str, float] = {
    "name": 3.0,
    "description": 2.0,
    "tags": 1.5,
    "params": 1.0,
    "search_hint": 2.0,
}

_SPLIT_RE = re.compile(r"[_\-]+")

TOOL_DISCOVERY_NAME = "discover_tools"


def _tool_name_to_text(name: str) -> str:
    """Convert a tool name like ``read_file`` to ``read file``."""
    return _SPLIT_RE.sub(" ", name)


def _extract_param_names(tool: Tool) -> str:
    """Extract parameter names from a tool's JSON schema, excluding ``toolcall_reason``."""
    props = tool.parameters.get("properties", {})
    return " ".join(k for k in props if k != "toolcall_reason")


def _tool_to_fields(tool: Tool) -> dict[str, str]:
    """Build a multi-field document from a Tool for BM25F indexing."""
    return {
        "name": _tool_name_to_text(tool.name),
        "description": tool.description or "",
        "tags": " ".join(tool.metadata.all_tags) if tool.metadata else "",
        "params": _extract_param_names(tool),
        "search_hint": tool.metadata.search_hint if tool.metadata else "",
    }


class ToolDiscoveryTool:
    """Discover registered tools by exact name or natural language query.

    Indexes tool name, description, tags, parameter names, and
    ``search_hint`` from :class:`~toolregistry.ToolMetadata` into a
    BM25F multi-field sparse index.

    The :meth:`discover` method first attempts an exact name match.
    If the query matches a registered tool name, its full schema is
    returned immediately.  Otherwise a BM25 fuzzy search is performed.

    Example::

        from toolregistry import ToolRegistry
        from toolregistry.tool_discovery import ToolDiscoveryTool

        registry = ToolRegistry()
        registry.register(my_func)

        discoverer = ToolDiscoveryTool(registry)
        results = discoverer.discover("add numbers")

    Args:
        registry: The tool registry to index.
        field_weights: Optional per-field BM25F boost weights.
            Defaults to ``{"name": 3.0, "description": 2.0,
            "tags": 1.5, "params": 1.0, "search_hint": 2.0}``.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        field_weights: dict[str, float] | None = None,
    ) -> None:
        self._registry = registry
        self._field_weights = field_weights or dict(_DEFAULT_FIELD_WEIGHTS)
        self._index = SparseIndex(field_weights=self._field_weights)
        self.rebuild_index()

    def rebuild_index(self) -> None:
        """Rebuild the search index from current registry state.

        Clears the existing index and re-indexes every tool currently
        registered in the associated :class:`~toolregistry.ToolRegistry`.
        """
        # Reset index with same config
        self._index = SparseIndex(field_weights=self._field_weights)

        for name, tool in self._registry._tools.items():
            # Skip the discovery tool itself to avoid circular results
            if name == TOOL_DISCOVERY_NAME:
                continue
            fields = _tool_to_fields(tool)
            metadata: dict[str, Any] = {
                "namespace": tool.namespace,
                "deferred": tool.metadata.defer if tool.metadata else False,
            }
            self._index.add(name, fields, metadata=metadata)

    def discover(
        self,
        query: str,
        top_k: int = 10,
        api_format: API_FORMATS = "openai-chat",
    ) -> list[dict[str, Any]]:
        """Discover tools by exact name or natural language query.

        If *query* exactly matches a registered tool name, a single
        result with the full tool schema is returned.  Otherwise a
        BM25 fuzzy search is performed over tool names, descriptions,
        tags, parameter names, and search hints.

        Args:
            query: Tool name (exact match) or natural language query.
            top_k: Maximum number of results for fuzzy search.
            api_format: Target API format for schema generation.
                Defaults to ``"openai-chat"``.

        Returns:
            List of dicts with keys:

            - ``name`` (str): Tool name.
            - ``description`` (str): Tool description.
            - ``score`` (float): BM25 relevance score (1.0 for exact).
            - ``namespace`` (str | None): Tool namespace.
            - ``deferred`` (bool): Whether the tool is deferred.
            - ``schema`` (dict): Full tool schema (only for deferred
              tools in fuzzy mode; always included for exact match).
        """
        # 1. Exact match: return full schema immediately
        tool = self._registry.get_tool(query)
        if tool is not None and query != TOOL_DISCOVERY_NAME:
            is_deferred = tool.metadata.defer if tool.metadata else False
            return [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "score": 1.0,
                    "namespace": tool.namespace,
                    "deferred": is_deferred,
                    "schema": tool.get_schema(api_format),
                }
            ]

        # 2. Fuzzy search via BM25
        results = self._index.search(query, top_k=top_k)
        out: list[dict[str, Any]] = []
        for r in results:
            tool = self._registry.get_tool(r.doc_id)
            is_deferred = r.metadata.get("deferred", False) if r.metadata else False
            entry: dict[str, Any] = {
                "name": r.doc_id,
                "description": tool.description if tool else "",
                "score": r.score,
                "namespace": r.metadata.get("namespace") if r.metadata else None,
                "deferred": is_deferred,
            }
            if is_deferred and tool is not None:
                entry["schema"] = tool.get_schema(api_format)
            out.append(entry)
        return out
