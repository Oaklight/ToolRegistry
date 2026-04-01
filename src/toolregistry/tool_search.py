"""Natural language tool search using BM25 sparse index.

Provides :class:`ToolSearchTool` which indexes all tools in a
:class:`~toolregistry.ToolRegistry` and exposes a
:meth:`~ToolSearchTool.search` method that LLMs can call to discover
relevant tools by natural language query.

The search backend is a vendored copy of *zerodep*'s ``SparseIndex``
(BM25/BM25F scoring, zero external dependencies).
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

from ._sparse_search import SparseIndex

if TYPE_CHECKING:
    from .tool import Tool
    from .tool_registry import ToolRegistry

_DEFAULT_FIELD_WEIGHTS: dict[str, float] = {
    "name": 3.0,
    "description": 2.0,
    "tags": 1.5,
    "params": 1.0,
    "search_hint": 2.0,
}

_SPLIT_RE = re.compile(r"[_\-]+")


def _tool_name_to_text(name: str) -> str:
    """Convert a tool name like ``read_file`` to ``read file``."""
    return _SPLIT_RE.sub(" ", name)


def _extract_param_names(tool: Tool) -> str:
    """Extract parameter names from a tool's JSON schema, excluding ``thought``."""
    props = tool.parameters.get("properties", {})
    return " ".join(k for k in props if k != "thought")


def _tool_to_fields(tool: Tool) -> dict[str, str]:
    """Build a multi-field document from a Tool for BM25F indexing."""
    return {
        "name": _tool_name_to_text(tool.name),
        "description": tool.description or "",
        "tags": " ".join(tool.metadata.all_tags) if tool.metadata else "",
        "params": _extract_param_names(tool),
        "search_hint": tool.metadata.search_hint if tool.metadata else "",
    }


class ToolSearchTool:
    """Search registered tools by natural language query using BM25.

    Indexes tool name, description, tags, parameter names, and
    ``search_hint`` from :class:`~toolregistry.ToolMetadata` into a
    BM25F multi-field sparse index.

    Example::

        from toolregistry import ToolRegistry
        from toolregistry.tool_search import ToolSearchTool

        registry = ToolRegistry()
        registry.register(my_func)

        searcher = ToolSearchTool(registry)
        results = searcher.search("add numbers")

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
            fields = _tool_to_fields(tool)
            metadata: dict[str, Any] = {
                "namespace": tool.namespace,
                "deferred": tool.metadata.defer if tool.metadata else False,
            }
            self._index.add(name, fields, metadata=metadata)

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Search tools matching the query.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.

        Returns:
            List of dicts with keys:

            - ``name`` (str): Tool name.
            - ``description`` (str): Tool description.
            - ``score`` (float): BM25 relevance score.
            - ``namespace`` (str | None): Tool namespace.
            - ``deferred`` (bool): Whether the tool is deferred.
        """
        results = self._index.search(query, top_k=top_k)
        out: list[dict[str, Any]] = []
        for r in results:
            tool = self._registry.get_tool(r.doc_id)
            out.append(
                {
                    "name": r.doc_id,
                    "description": tool.description if tool else "",
                    "score": r.score,
                    "namespace": r.metadata.get("namespace") if r.metadata else None,
                    "deferred": r.metadata.get("deferred", False)
                    if r.metadata
                    else False,
                }
            )
        return out
