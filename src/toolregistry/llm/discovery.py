"""Natural language tool discovery using BM25 sparse index.

Provides :class:`ToolDiscoveryTool` which indexes all tools in a
:class:`~toolregistry.ToolRegistry` and exposes a
:meth:`~ToolDiscoveryTool.discover` method that LLMs can call to find
relevant tools by exact name or natural language query.

The search backend is a vendored copy of *zerodep*'s ``SparseIndex``
(BM25/BM25F scoring, zero external dependencies).
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import TYPE_CHECKING, Annotated, Any

# ``_default_tokenize`` is a private helper of the vendored search backend.
# The coupling is intra-repo: `sparse_search.py` ships in this wheel and is
# pinned by its ``# /// zerodep / version = "0.4.0"`` banner.  Importing it
# keeps our tokenizer byte-identical to the default; drift is caught by
# tests/test_tool_discovery.py::TestDiscoveryCjkSearch::test_ascii_tokenization_unchanged.
from .._vendor.sparse_search import SparseIndex, _default_tokenize
from .._vendor.validate import Ge, Match, MinLen
from ..events import ChangeEvent, ChangeEventType
from .tool_calls import API_FORMATS

if TYPE_CHECKING:
    from ..tool import Tool
    from ..tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

_DEFAULT_FIELD_WEIGHTS: dict[str, float] = {
    "name": 3.0,
    "description": 2.0,
    "tags": 1.5,
    "params": 1.0,
    "search_hint": 2.0,
}

_SPLIT_RE = re.compile(r"[_\-]+")

# CJK scripts whose characters the default ``[\w]+`` tokenizer lumps into a
# single token.  Covers Hiragana/Katakana, CJK Unified Ideographs (plus
# Extension A and Compatibility Ideographs for Chinese/Japanese), and Hangul
# syllables for Korean.
_CJK_RE = re.compile("[぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]+")

#: Fraction of the best hit's score below which a fuzzy result is dropped.
#: BM25 scores are not comparable across queries, so the floor is relative:
#: a query with one strong match no longer pads the answer with unrelated
#: tools that merely share a token (Oaklight/ToolRegistry#330).
DEFAULT_MIN_SCORE_RATIO = 0.3

#: Fraction of the corpus a query token may appear in before it stops
#: carrying signal.  Tokens present in at least this fraction are dropped
#: from the query, so a prose word such as "for" — present in most tool
#: descriptions, and therefore scoring every tool that contains it — cannot
#: produce filler hits (#332).
#: ``0`` disables the filter.  This is corpus-adaptive, so no English
#: stopword list is needed and the same rule applies to any language.
DEFAULT_MAX_DF_RATIO = 0.5

#: A token must occur in at least this many indexed tools before its document
#: frequency is trusted as a signal.  In a small registry a word shared by two
#: of four tools is 50%, which the ratio alone would treat as ubiquitous even
#: though it is the very word a user searches for (#334).  Expressed as an
#: absolute count rather than a corpus size so the filter still catches filler
#: in small corpora.
_MIN_DF_FOR_FILTER = 3

TOOL_DISCOVERY_NAME = "discover_tools"
TOOL_CALL_DEFERRED_NAME = "call_deferred"

INFRASTRUCTURE_TOOLS = frozenset({TOOL_DISCOVERY_NAME, TOOL_CALL_DEFERRED_NAME})

#: Registry events that change the searchable set or an indexed field, so the
#: index must be rebuilt before the next search.
_INDEX_AFFECTING_EVENTS = frozenset(
    {
        ChangeEventType.REGISTER,
        ChangeEventType.UNREGISTER,
        ChangeEventType.OVERRIDE,
        ChangeEventType.ENABLE,
        ChangeEventType.DISABLE,
        ChangeEventType.METADATA_UPDATE,
    }
)

_BASE_DISCOVERY_DESCRIPTION = (
    "Discover registered tools by exact name or natural language query. "
    "Use this to inspect a specific tool by name (returns full schema) or "
    "to search for relevant tools when you need a capability not visible in "
    "your current tool list. Queries match each tool's registered metadata "
    "(name, description, tags, parameters, search hint); English keywords "
    "match most reliably."
)

BASE_CALL_DEFERRED_DESCRIPTION = (
    "Call a deferred tool by name. Use this after discover_tools returns "
    "a deferred tool's schema — pass the tool name as _target_tool and "
    "its parameters as keyword arguments. "
    "Example: call_deferred(_target_tool='search', query='hello')"
)


def _tool_name_to_text(name: str) -> str:
    """Convert a tool name like ``read_file`` to ``read file``."""
    return _SPLIT_RE.sub(" ", name)


def _normalize_tool_name(name: str) -> str:
    """Normalize a tool name for client-tolerant matching.

    Some MCP clients rewrite ``/`` and ``-`` into ``_`` in function names,
    so the spelling the model holds may not match the registered name.
    Lowercasing both sides makes the comparison case-insensitive too.

    Args:
        name: A tool name in any spelling.

    Returns:
        The normalized name used for lookup and suggestion comparison.
    """
    return name.replace("/", "_").replace("-", "_").lower()


def _tokenize_for_search(text: str) -> list[str]:
    """Tokenize search text, adding CJK bigrams on top of default tokens.

    ASCII/alphanumeric text tokenizes exactly like the vendored
    ``_default_tokenize`` (Unicode ``[\\w]+`` split + lowercasing), so
    English ranking is unchanged.  For text containing CJK characters the
    default tokenizer would emit a contiguous ideograph run as one
    unmatchable token, so this adds character bigrams within each CJK run
    (e.g. ``天气`` yields ``天气``; ``天气查询`` yields ``天气``, ``气查``,
    ``查询``).  Bigrams never span runs, so a comma, space or ASCII text
    between two CJK runs cannot produce a token the source text lacks.

    Args:
        text: Raw document or query text.

    Returns:
        List of search tokens.
    """
    tokens = _default_tokenize(text)
    extra: list[str] = []
    for run in _CJK_RE.findall(text):
        # ``_CJK_RE`` matches maximal runs; bigram within each run only.
        if len(run) == 1:
            extra.append(run)
        else:
            extra.extend(run[i : i + 2] for i in range(len(run) - 1))
    if not extra:
        return tokens

    # Preserve the default tokens (which still help for exact CJK runs) and
    # append only the bigrams not already present.
    seen = set(tokens)
    for token in extra:
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def _with_output_schema(tool: Tool, schema: dict[str, Any]) -> dict[str, Any]:
    """Attach a tool's declared output schema to its generated schema.

    A tool declares its result shape in ``ToolMetadata.extra["output_schema"]``
    (the same field the server publishes as MCP ``outputSchema``).  Provider
    tool definitions have no slot for it, so a discovery result would otherwise
    describe only the arguments — leaving a model unable to tell what a
    deferred tool returns, even though the tool emits structured content.

    The key is placed beside the input schema for the target format: inside
    ``function`` for OpenAI-style definitions, at the top level for the flat
    ``openai-responses``, Anthropic and Gemini shapes.

    Args:
        tool: The tool the schema was generated from.
        schema: Schema returned by :meth:`Tool.get_schema`.

    Returns:
        The same schema dict, extended in place when the tool declares an
        output schema.
    """
    extra = tool.metadata.extra if tool.metadata else None
    output_schema = (extra or {}).get("output_schema")
    if not output_schema:
        return schema
    function = schema.get("function")
    if isinstance(function, dict):
        function["output_schema"] = output_schema
    else:
        schema["output_schema"] = output_schema
    return schema


def _extract_param_names(tool: Tool) -> str:
    """Extract parameter names from a tool's JSON schema."""
    props = tool.parameters.get("properties", {})
    return " ".join(props)


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

    Only enabled tools are indexed.  Tools disabled at the method level
    or via their namespace are excluded, matching
    :meth:`ToolRegistry.get_deferred_summaries`.

    Example::

        from toolregistry import ToolRegistry
        from toolregistry.llm.discovery import ToolDiscoveryTool

        registry = ToolRegistry()
        registry.register(my_func)

        discoverer = ToolDiscoveryTool(registry)
        results = discoverer.discover("add numbers")

    Args:
        registry: The tool registry to index.
        field_weights: Optional per-field BM25F boost weights.
            Defaults to ``{"name": 3.0, "description": 2.0,
            "tags": 1.5, "params": 1.0, "search_hint": 2.0}``.
        min_score_ratio: Drop fuzzy hits scoring below this fraction of the
            best hit (default :data:`DEFAULT_MIN_SCORE_RATIO`).  ``0``
            disables the floor and returns the raw ``top_k`` list.  The
            exact-name match is unaffected.
        max_df_ratio: Drop query tokens that appear in more than this
            fraction of the indexed tools (default
            :data:`DEFAULT_MAX_DF_RATIO`).  ``0`` disables the filter.

    Raises:
        ValueError: If either ratio is outside ``[0.0, 1.0]`` or is a
            ``bool``.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        field_weights: dict[str, float] | None = None,
        min_score_ratio: float = DEFAULT_MIN_SCORE_RATIO,
        max_df_ratio: float = DEFAULT_MAX_DF_RATIO,
    ) -> None:
        self._validate_ratio("min_score_ratio", min_score_ratio)
        self._validate_ratio("max_df_ratio", max_df_ratio)
        self._registry = registry
        self._min_score_ratio = min_score_ratio
        self._max_df_ratio = max_df_ratio
        # Document frequency over the indexed tools, rebuilt with the index.
        self._doc_freq: dict[str, int] = {}
        self._doc_count = 0
        self._field_weights = field_weights or dict(_DEFAULT_FIELD_WEIGHTS)
        self._index = SparseIndex(
            field_weights=self._field_weights,
            tokenize=_tokenize_for_search,
        )
        # Set by _mark_dirty() on enable/disable/metadata changes and cleared
        # by rebuild_index(); discover() rebuilds lazily so a bulk change pays
        # one rebuild, not one per event.
        self._index_dirty = False
        self.rebuild_index()
        # Subscribe here rather than relying on ToolRegistry to do it: the
        # documented usage constructs a discoverer directly, and that path
        # used to go stale as soon as a tool was registered (#334).
        self._on_change_event = self._handle_registry_change
        self._closed = False
        self._registry.on_change(self._on_change_event)

    @staticmethod
    def _validate_ratio(name: str, value: float) -> None:
        """Reject ratios outside ``[0, 1]``, including ``bool``.

        ``True`` passes a naive range check and silently means ``1.0``;
        a caller almost certainly passed the wrong keyword.
        """
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(
                f"{name} must be a number between 0.0 and 1.0, got {value!r}"
            )
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")

    def rebuild_index(self) -> None:
        """Rebuild the search index from current registry state.

        Clears the existing index and re-indexes every enabled tool
        currently registered in the associated
        :class:`~toolregistry.ToolRegistry`.  Disabled tools (including
        those disabled through their namespace) are skipped so the index
        agrees with :meth:`ToolRegistry.get_deferred_summaries`.  Also
        updates the ``discover_tools`` description with current deferred
        tool summaries so LLMs are aware of hidden capabilities.
        """
        # Reset index with same config
        self._index = SparseIndex(
            field_weights=self._field_weights,
            tokenize=_tokenize_for_search,
        )

        self._doc_freq = {}
        self._doc_count = 0
        for name, tool in self._registry._tools.items():
            if name in INFRASTRUCTURE_TOOLS:
                continue
            if not self._registry.is_enabled(name):
                continue
            fields = _tool_to_fields(tool)
            metadata: dict[str, Any] = {
                "namespace": tool.namespace,
                "deferred": tool.metadata.defer if tool.metadata else False,
            }
            self._index.add(name, fields, metadata=metadata)

            # Union of the fields' tokens: a term the tool mentions in any
            # field counts once for this document, matching the index's own
            # document frequency.
            tokens: set[str] = set()
            for value in fields.values():
                tokens.update(_tokenize_for_search(value))
            for token in tokens:
                self._doc_freq[token] = self._doc_freq.get(token, 0) + 1
            self._doc_count += 1

        self._index_dirty = False
        self._sync_description()

    def _handle_registry_change(self, event: ChangeEvent) -> None:
        """Mark the index stale when the searchable set changes.

        Registered as a change callback by :meth:`__init__`, so both a
        directly constructed discoverer and one created by
        :meth:`ToolRegistry.enable_tool_discovery` stay in sync.  Changes to
        the discovery tools themselves are ignored to avoid a rebuild loop
        through :meth:`_sync_description`.

        Args:
            event: The registry change that was emitted.
        """
        if event.tool_name in INFRASTRUCTURE_TOOLS:
            return
        if event.event_type in _INDEX_AFFECTING_EVENTS:
            self._mark_dirty()

    def close(self) -> None:
        """Stop following registry changes.

        Idempotent.  The current index is kept, so searches still work;
        changes made to the registry afterwards are no longer reflected.
        """
        if self._closed:
            return
        self._registry.remove_on_change(self._on_change_event)
        self._closed = True

    def _mark_dirty(self) -> None:
        """Mark the search index stale after a registry change.

        Called on enable/disable/metadata changes.  The rebuild is deferred
        to the next :meth:`discover` call so a bulk change (e.g. disabling
        many tools by tag) pays one rebuild instead of one per event.  The
        deferred summaries are refreshed eagerly because the ``discover_tools``
        description is read before any call.
        """
        self._index_dirty = True
        self._sync_description()

    def _sync_description(self) -> None:
        """Update tool descriptions with deferred tool summaries.

        Updates both ``discover_tools`` and ``call_deferred`` descriptions
        so LLMs know which capabilities exist but are not shown in full.
        No-ops if the tools are not yet registered.
        """
        discovery_tool = self._registry._tools.get(TOOL_DISCOVERY_NAME)
        call_deferred_tool = self._registry._tools.get(TOOL_CALL_DEFERRED_NAME)

        summaries = self._registry.get_deferred_summaries()
        if summaries:
            tool_list = []
            for s in summaries:
                desc = s["description"]
                suffix = f": {desc}" if desc else ""
                tool_list.append(f"- {s['name']}{suffix}")
            tool_list_str = "\n".join(tool_list)

            if discovery_tool is not None:
                new_desc = (
                    _BASE_DISCOVERY_DESCRIPTION + "\n\nTools available on demand "
                    "(call discover_tools for full schema):\n" + tool_list_str
                )
                self._registry._replace_tool(TOOL_DISCOVERY_NAME, description=new_desc)
            if call_deferred_tool is not None:
                new_desc = (
                    BASE_CALL_DEFERRED_DESCRIPTION
                    + "\n\nCurrently deferred:\n"
                    + tool_list_str
                )
                self._registry._replace_tool(
                    TOOL_CALL_DEFERRED_NAME, description=new_desc
                )
        else:
            if discovery_tool is not None:
                self._registry._replace_tool(
                    TOOL_DISCOVERY_NAME, description=_BASE_DISCOVERY_DESCRIPTION
                )
            if call_deferred_tool is not None:
                new_desc = (
                    BASE_CALL_DEFERRED_DESCRIPTION
                    + " No deferred tools currently available."
                )
                self._registry._replace_tool(
                    TOOL_CALL_DEFERRED_NAME, description=new_desc
                )

    def discover(
        self,
        # ``Match`` uses ``re.fullmatch``, so the pattern must describe the
        # whole query.  ``\S`` alone only accepts a single character (#326);
        # require at least one non-whitespace character and allow whitespace
        # anywhere else.  ``[\s\S]`` rather than ``.`` so embedded newlines
        # (models sometimes emit them) are accepted, and no inline ``(?s)``
        # flag, which JSON Schema ``pattern`` dialects do not all support.
        query: Annotated[str, MinLen(1), Match(r"[\s\S]*\S[\s\S]*")],
        top_k: Annotated[int, Ge(1)] = 10,
        api_format: API_FORMATS = "openai-chat",
    ) -> list[dict[str, Any]]:
        """Discover tools by exact name or natural language query.

        If *query* exactly matches an enabled registered tool name, a
        single result with the full tool schema is returned.  Otherwise a
        BM25 fuzzy search is performed over tool names, descriptions,
        tags, parameter names, and search hints, and hits scoring below
        ``min_score_ratio`` of the best hit are dropped, so a query with
        one clear match is not padded with unrelated tools.

        Args:
            query: Tool name (exact match) or natural language query.
                Must contain at least one non-whitespace character.
            top_k: Maximum number of results for fuzzy search. Must be
                at least 1.
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

        Raises:
            ValueError: If *query* is empty or whitespace-only, or if
                *top_k* is less than 1.
        """
        if not query or not query.strip():
            raise ValueError(
                "empty query — pass a capability keyword, e.g. 'web search'. "
                "Queries are matched against English tool descriptions."
            )
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")

        # Rebuild lazily if a prior enable/disable/metadata change marked the
        # index stale, so results never reflect a stale document.
        if self._index_dirty:
            self.rebuild_index()

        exact = self._exact_match(query, api_format)
        if exact is not None:
            return [exact]

        tokens = self._filter_query_tokens(query)
        if not tokens:
            logger.warning(
                "discover(%r): every query token appears in most registered "
                "tools, so none carries signal; pass a more specific query",
                query,
            )
            return []

        out = self._fuzzy_match(" ".join(tokens), top_k, api_format)
        if not out:
            logger.warning(
                "discover(%r) matched no registered tool metadata "
                "(name/description/tags/params/search_hint); English keywords "
                "match most reliably",
                query,
            )
        return out

    def _exact_match(
        self, query: str, api_format: API_FORMATS
    ) -> dict[str, Any] | None:
        """Return a full-schema result if *query* names an enabled tool.

        Prefers the exact registered spelling, then falls back to a
        normalized match so a client-rewritten name resolves here exactly as
        it does in :meth:`call_deferred` (and case-insensitively).

        Args:
            query: Tool name in any spelling.
            api_format: Target API format for schema generation.

        Returns:
            A single result dict, or ``None`` when no enabled tool matches.
        """
        exact = self._registry.get_tool(query)
        canonical = (
            exact.name if exact is not None else self._resolve_registered_name(query)
        )
        if canonical is None:
            return None
        tool = self._registry.get_tool(canonical)
        if (
            tool is None
            or tool.name in INFRASTRUCTURE_TOOLS
            or not self._registry.is_enabled(tool.name)
        ):
            return None
        is_deferred = tool.metadata.defer if tool.metadata else False
        return {
            "name": tool.name,
            "description": tool.description or "",
            "score": 1.0,
            "namespace": tool.namespace,
            "deferred": is_deferred,
            "schema": _with_output_schema(tool, tool.get_schema(api_format)),
        }

    def _filter_query_tokens(self, query: str) -> list[str]:
        """Drop query tokens that appear in too many indexed tools.

        A word the corpus uses almost everywhere ("for" in tool
        descriptions) carries little discriminative signal, yet BM25 still
        scores every document containing it — enough, in a small corpus, to
        fill the result list with near-tied filler (#332).  Filtering by
        document frequency is corpus-adaptive, unlike a language-specific
        stopword list.

        A token is only treated as filler once it occurs in at least
        :data:`_MIN_DF_FOR_FILTER` tools *and* in at least ``max_df_ratio``
        of them.  A single-token query is never filtered: one word is a
        capability keyword rather than prose padded with stopwords, so
        dropping it would make the phrase unfindable (#334).

        Args:
            query: The raw query string.

        Returns:
            The surviving tokens, or an empty list when no token is
            discriminative enough to justify a search.
        """
        tokens = _tokenize_for_search(query)
        if self._max_df_ratio <= 0 or len(tokens) < 2:
            return tokens

        kept = [token for token in tokens if not self._is_ubiquitous(token)]
        if len(kept) != len(tokens):
            logger.debug(
                "discover(%r): dropped %d common token(s) %s",
                query,
                len(tokens) - len(kept),
                sorted(set(tokens) - set(kept)),
            )
        return kept

    def _is_ubiquitous(self, token: str) -> bool:
        """Return whether *token* appears in too many tools to carry signal.

        Args:
            token: A tokenized query term.

        Returns:
            ``True`` when the token occurs in at least
            :data:`_MIN_DF_FOR_FILTER` tools and in at least
            ``max_df_ratio`` of the indexed corpus.
        """
        doc_freq = self._doc_freq.get(token, 0)
        if doc_freq < _MIN_DF_FOR_FILTER:
            return False
        return doc_freq / self._doc_count >= self._max_df_ratio

    def _fuzzy_match(
        self, query: str, top_k: int, api_format: API_FORMATS
    ) -> list[dict[str, Any]]:
        """Return BM25 fuzzy results, attaching metadata to each hit.

        Args:
            query: Natural language query.
            top_k: Maximum number of results.
            api_format: Target API format for schema generation.

        Returns:
            List of result dicts, best first.
        """
        hits = self._index.search(query, top_k=top_k)
        if hits and self._min_score_ratio > 0.0:
            floor = hits[0].score * self._min_score_ratio
            kept = [h for h in hits if h.score >= floor]
            if len(kept) != len(hits):
                logger.debug(
                    "discover(%r): dropped %d of %d hit(s) below %.2f x best",
                    query,
                    len(hits) - len(kept),
                    len(hits),
                    self._min_score_ratio,
                )
            hits = kept

        out: list[dict[str, Any]] = []
        for r in hits:
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
                entry["schema"] = _with_output_schema(tool, tool.get_schema(api_format))
            out.append(entry)
        return out

    def _resolve_registered_name(self, requested: str) -> str | None:
        """Resolve a requested tool name to its registered spelling.

        Clients commonly rewrite ``/`` and ``-`` as ``_`` in function
        names, so the name held by the model may not equal the registry
        key.  This matches on the normalized form and returns the
        registry's own spelling.

        Args:
            requested: The tool name as supplied by the caller.

        Returns:
            The registered name, or ``None`` if no registered tool
            normalizes to the same form.
        """
        target = _normalize_tool_name(requested)
        for name in self._registry._tools:
            if _normalize_tool_name(name) == target:
                return name
        return None

    def _suggest_tool_names(self, requested: str, limit: int = 3) -> list[str]:
        """Return close registered names for a failed lookup.

        Comparison happens in normalized space so a client-rewritten name
        such as ``weather_get_current`` still suggests ``weather-get-current``.
        Suggestions are reported using the registered spelling.

        Args:
            requested: The tool name that failed to resolve.
            limit: Maximum number of suggestions.

        Returns:
            Registered tool names, closest first.
        """
        by_normalized: dict[str, str] = {}
        for name in self._registry._tools:
            by_normalized.setdefault(_normalize_tool_name(name), name)
        matches = difflib.get_close_matches(
            _normalize_tool_name(requested),
            list(by_normalized),
            n=limit,
            cutoff=0.5,
        )
        return [by_normalized[m] for m in matches]

    def call_deferred(self, _target_tool: str, **kwargs: Any) -> Any:
        # **kwargs produces additionalProperties: true in the JSON Schema,
        # which is essential for this proxy to accept arbitrary parameters.
        """Call a deferred tool by name with the given arguments.

        Intended as a proxy for MCP clients that cannot dynamically
        register tools discovered via :meth:`discover`.  The LLM
        discovers a deferred tool's schema, then invokes this method
        with the tool name and its parameters as keyword arguments.

        Delegates to :meth:`ToolRegistry._invoke_raw` which runs the
        full pipeline (permissions, execution backend, logging) and
        returns the raw Python value — the outer ``execute_tool_calls``
        handles result wrapping.

        The target name is normalized before lookup (``/`` and ``-`` are
        treated like ``_``, and case is ignored) so a name rewritten by an
        MCP client still resolves to the registered tool.  On a miss, the
        error lists close registered names so the model can self-correct
        in one turn.

        The first parameter is named ``_target_tool`` (not ``tool_name``)
        to avoid shadowing a deferred tool that has its own ``tool_name``
        parameter.

        Args:
            _target_tool: Registered name of the deferred tool to call.
            **kwargs: Parameters forwarded to the target tool.

        Returns:
            The tool's raw result on success.

        Raises:
            KeyError: If the tool is not found.
            ValueError: If the tool is not deferred.
            Exception: Any exception raised by the target tool.
        """
        exact = self._registry.get_tool(_target_tool)
        canonical = (
            exact.name
            if exact is not None
            else self._resolve_registered_name(_target_tool)
        )
        if canonical is None:
            suggestions = self._suggest_tool_names(_target_tool)
            message = f"tool '{_target_tool}' not found in registry."
            if suggestions:
                message += f" Did you mean: {', '.join(suggestions)}?"
            raise KeyError(message)

        target = self._registry.get_tool(canonical)
        assert target is not None  # canonical came from the registry
        is_deferred = target.metadata.defer if target.metadata else False
        if not is_deferred:
            raise ValueError(
                f"'{canonical}' is not a deferred tool — "
                f"call it directly instead of using call_deferred."
            )

        return self._registry._invoke_raw(canonical, kwargs)
