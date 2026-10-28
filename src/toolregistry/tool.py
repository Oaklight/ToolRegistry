import copy
import dataclasses
import inspect
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Literal, TypeVar, get_type_hints
from collections.abc import Callable

from ._names import NameSeparator, qualify_name
from ._validation import HINT_METADATA_FIELDS, validate_metadata_field
from .parameter_models import (
    _generate_parameters_model,
    _normalize_union_keywords,
    _simplify_nullable_schemas,
)
from .llm.tool_calls import API_FORMATS
from .tool_wrapper import BaseToolWrapper, _FunctionToolWrapper
from .utils import compute_schema_hash, normalize_tool_name


_ToolT = TypeVar("_ToolT", bound="Tool")


def _apply_flattened_parameters(
    result: dict[str, Any], parameters: dict[str, Any], api_format: str
) -> None:
    """Restore ToolRegistry's flattened schema into a provider definition.

    llm-rosetta sanitizes parameter schemas again when converting an IR tool
    definition.  Releases before 0.14 collapse multi-branch unions (such as
    ``float | list[float] | None``) to their first branch, dropping valid
    input shapes.  ToolRegistry already flattened and sanitized *parameters*
    at construction time, so use that schema for providers whose dialect
    accepts ``anyOf``/``oneOf`` (OpenAI Chat/Responses, Anthropic, Google
    Interactions).  When rosetta already produced the same schema
    (llm-rosetta#747 and later), nothing is replaced.

    Gemini is intentionally excluded: whatever rosetta emits for Google
    GenAI is kept.  Older rosetta releases collapse the union there; newer
    releases may preserve it, in which case Gemini follows rosetta.
    """
    if api_format == "openai-chat":
        target = result["function"]
        key = "parameters"
    elif api_format == "anthropic":
        target = result
        key = "input_schema"
    elif api_format in ("openai-responses", "google-interactions"):
        target = result
        key = "parameters"
    else:
        return

    if target.get(key) != parameters:
        target[key] = copy.deepcopy(parameters)


class ToolTag(str, Enum):
    """Predefined tags for common tool characteristics.

    Inherits from ``str`` so that ``ToolTag.READ_ONLY == "read_only"`` is
    ``True``, making serialization and comparison with custom string tags
    seamless.
    """

    READ_ONLY = "read_only"
    DESTRUCTIVE = "destructive"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    SLOW = "slow"
    PRIVILEGED = "privileged"


TOOLCALL_REASON_PROPERTY: dict[str, str] = {
    "type": "string",
    "description": "Why you chose this tool and what you expect from it.",
}
"""Schema snippet injected into every tool's ``parameters.properties``
so that LLMs can articulate the rationale for each tool call.

Inspired by thought-augmented tool calling (https://arxiv.org/abs/2601.18282)
but uses a unique field name to avoid collisions with native tool parameters.
"""


@dataclass(frozen=True)
class ToolMetadata:
    """Behavioral and classification metadata for a Tool.

    Note:
        Frozen semantics are shallow: field reassignment is prevented, but
        the containers (``tags``, ``custom_tags``, ``extra``) are still
        mutable.  They are copied on construction, so a
        ``dataclasses.replace`` copy never shares them with the original.
        In-place mutation of a live instance remains unsupported because it
        bypasses change events; use
        :meth:`ToolRegistry.update_tool_metadata` (or
        ``update_namespace_metadata``) to change metadata on a registered
        tool.

    Attributes:
        is_async: Whether the tool requires async execution.
        is_concurrency_safe: Whether the tool can be run concurrently.
        timeout: Per-call timeout in seconds. None means no limit.
        locality: Execution location requirement. ``"local"`` for tools that
            must run on the user's machine (e.g. file-system, shell),
            ``"remote"`` for tools best served by a remote server
            (e.g. web search), ``"any"`` (default) for location-agnostic tools.
        max_result_size: Maximum result size in characters. When a tool's
            result exceeds this limit, it is automatically truncated and
            the full output is persisted to a temporary file. Only
            effective when executed through
            ``ToolRegistry.execute_tool_calls()``. None means no limit.
        tags: Predefined tags from ToolTag enum.
        custom_tags: User-defined free-form string tags.
        source: Origin of the tool (e.g. ``"native"``, ``"mcp"``,
            ``"openapi"``, ``"langchain"``).
        source_detail: Extra detail about the tool's origin (e.g. a
            transport URI, spec URL, or class name).
        schema_hash: SHA-256 hex digest of the canonical JSON Schema for
            the tool's parameters.  Computed at registration time and
            updated on refresh.
        last_refreshed_at: ISO 8601 timestamp of the most recent
            successful refresh, or empty string for tools that have
            never been refreshed.
        extra: Arbitrary key-value pairs for application-specific use.
    """

    is_async: bool = False
    is_concurrency_safe: bool = True
    timeout: float | None = None
    locality: Literal["local", "remote", "any"] = "any"
    max_result_size: int | None = None

    tags: set[ToolTag] = field(default_factory=set)
    custom_tags: set[str] = field(default_factory=set)

    source: str = "native"
    """Origin of the tool.

    Indicates which integration registered the tool.  Standard values:
    ``"native"``, ``"mcp"``, ``"openapi"``, ``"langchain"``.
    """

    source_detail: str = ""
    """Extra detail about the tool's origin.

    Free-form string providing additional context about where the tool
    came from, e.g. a transport URI for MCP tools, a spec URL for
    OpenAPI tools, or a class name for LangChain tools.
    """

    schema_hash: str = ""
    """SHA-256 hex digest of the canonical ``Tool.parameters`` JSON Schema.

    Computed at registration time and updated on refresh.  Enables
    fast equality checks (compare hashes) instead of deep dict
    comparison, and lets consumers detect schema changes without
    inspecting the full schema.

    If set before ``Tool.__init__`` runs, the value is trusted and
    not recomputed.
    """

    last_refreshed_at: str = ""
    """ISO 8601 timestamp of the last successful refresh.

    Empty string for tools that have never been refreshed (i.e.
    registered but never had ``refresh()`` called).  Set even when
    the refresh found no changes — "I checked and it's current"
    is valid freshness information.
    """

    extra: dict[str, Any] = field(default_factory=dict)

    defer: bool = False
    """Whether this tool should be deferred from the initial prompt.

    When ``True``, the tool's schema is excluded from the initial
    tool list sent to the LLM.  The LLM can discover it via
    ``ToolDiscoveryTool`` and have the schema injected on demand.
    """

    search_hint: str = ""
    """Free-form keywords to improve tool discoverability.

    Indexed by ``ToolDiscoveryTool`` alongside the tool's name,
    description, and tags.  Use this to add synonyms, related
    concepts, or domain-specific terms, e.g.
    ``"jupyter notebook ipynb cell"``.
    """

    think_augment: bool | None = None
    """Control thought-augmented tool calling for this tool.

    - ``None`` (default): follow the registry-level setting.
    - ``True``: always inject a ``toolcall_reason`` property into this
      tool's schema, regardless of the registry setting.
    - ``False``: never inject ``toolcall_reason`` into this tool's schema.

    Reference: https://arxiv.org/abs/2601.18282
    """

    natural_backend: Literal["inline", "thread", "process"] | None = None
    """Preferred execution backend for this tool.

    Resolved by ``ToolRegistry`` when no explicit ``execution_mode`` is
    given by the caller. ``None`` (default) means the registry chooses:
    single-tool ``invoke``/``ainvoke`` default to the inline backend,
    while ``execute_tool_calls`` uses the registry's default mode.

    Integration tools that are already isolated (MCP servers, remote
    HTTP APIs) set this to ``"inline"`` because pooling or pickling
    their transport would be wrong or impossible.
    """

    title: str | None = None
    """Human-readable display title for the tool.

    ``None`` (default) means no title was declared.  When set, transports
    may surface it to hosts as a display name distinct from the
    machine-readable ``name``.
    """

    read_only_hint: bool | None = None
    """Whether the tool only reads data and has no side effects.

    Tri-state: ``None`` (default) means *unset / unknown* — the tool makes
    no claim.  ``True`` and ``False`` are explicit declarations and stay
    distinguishable from ``None``.  When unset, the value is derived from
    :attr:`tags` (``ToolTag.READ_ONLY`` → ``True``) by
    :attr:`execution_hints`; an explicit value always wins over the tag.
    Resolving ``True`` also resolves an unset :attr:`destructive_hint` to
    ``False`` (see :attr:`execution_hints`).

    Maps to the MCP ``readOnlyHint`` annotation (MCP 2025-06-18), whose
    protocol default is ``false``.  Because a host may treat an absent
    hint as write-capable, emitting ``True`` for known read-only tools
    avoids a per-call approval prompt.
    """

    destructive_hint: bool | None = None
    """Whether the tool may perform destructive or irreversible updates.

    Tri-state, same contract as :attr:`read_only_hint`.  When unset, the
    value is derived from :attr:`tags` (``ToolTag.DESTRUCTIVE`` →
    ``True``), and to ``False`` when :attr:`read_only_hint` resolves
    ``True`` and nothing marks the tool destructive.

    Maps to the MCP ``destructiveHint`` annotation (MCP 2025-06-18),
    whose protocol default is ``true``.  ``None`` here means *unset*, not
    ``False``, so the transport adapter decides whether to emit it.
    """

    idempotent_hint: bool | None = None
    """Whether repeating the call with identical arguments has no
    additional effect.

    Tri-state, same contract as :attr:`read_only_hint`.  Not derived from
    tags — a ``FILE_SYSTEM`` or ``NETWORK`` tag does not imply
    idempotency.

    Maps to the MCP ``idempotentHint`` annotation (MCP 2025-06-18).
    """

    open_world_hint: bool | None = None
    """Whether the tool interacts with an open, external world (for
    example the public web) rather than a closed local domain.

    Tri-state, same contract as :attr:`read_only_hint`.  Not derived from
    tags — a ``NETWORK`` tag does not by itself imply an open world.

    Maps to the MCP ``openWorldHint`` annotation (MCP 2025-06-18), whose
    protocol default is ``true``.
    """

    _VALID_LOCALITY = {"local", "remote", "any"}
    _VALID_BACKEND = {"inline", "thread", "process", None}

    def __post_init__(self) -> None:
        # Frozen only prevents rebinding.  Copy the mutable containers so
        # every constructed instance -- including every dataclasses.replace
        # copy and the caller's input containers -- owns its own data.
        object.__setattr__(self, "tags", set(self.tags))
        object.__setattr__(self, "custom_tags", set(self.custom_tags))
        object.__setattr__(self, "extra", dict(self.extra))
        if self.locality not in self._VALID_LOCALITY:
            raise ValueError(
                f"Invalid locality {self.locality!r}, "
                f"must be one of {self._VALID_LOCALITY}"
            )
        if self.natural_backend not in self._VALID_BACKEND:
            raise ValueError(
                f"Invalid natural_backend {self.natural_backend!r}, "
                f"must be one of {self._VALID_BACKEND}"
            )
        for field_name in HINT_METADATA_FIELDS:
            validate_metadata_field(field_name, getattr(self, field_name))
        self._warn_if_contradictory_hints()

    @property
    def all_tags(self) -> set[str]:
        """Union of predefined and custom tags (all as str)."""
        return {
            t if isinstance(t, str) else t.value for t in self.tags
        } | self.custom_tags

    @property
    def execution_hints(self) -> dict[str, bool]:
        """Resolved execution hints, including tag-derived defaults.

        Returns only the hints that are actually determined, keyed by the
        snake_case :class:`ToolMetadata` field names.  A hint that is
        absent from the result is *unset* and must be distinguished from
        one explicitly set to ``False``.

        Derivation lives here and nowhere else.  An unset ``read_only_hint``
        resolves to ``True`` when ``ToolTag.READ_ONLY`` is present.  An
        unset ``destructive_hint`` resolves to ``True`` when
        ``ToolTag.DESTRUCTIVE`` is present, and to ``False`` when
        ``read_only_hint`` resolves to ``True`` with no destructive signal
        (tag or explicit value): MCP defaults ``destructiveHint`` to
        ``true``, so a read-only tool that left it unset would emit the
        contradictory pair ``readOnlyHint=true`` / ``destructiveHint=true``.
        An explicit field value always wins over the tag and over the
        derived complement.  ``idempotent_hint`` and ``open_world_hint``
        are never derived.

        The result is transport-neutral: the keys are core field names and
        map 1:1 onto protocol annotation names, so a transport (for example
        an MCP server adapter) can carry them straight onto
        ``readOnlyHint``, ``destructiveHint``, ``idempotentHint`` and
        ``openWorldHint``.  :attr:`title` is a display name rather than a
        hint and is exposed separately, not through this mapping.

        ``read_only_hint`` and ``destructive_hint`` are independent: the
        MCP hints do not override one another, and a tool that resolves
        both to ``True`` is self-contradictory.  That combination emits a
        :class:`UserWarning` when the metadata is built — after the
        complement rule above, it can only arise from an explicit
        ``destructive_hint=True`` alongside a read-only resolution.  See
        :meth:`_warn_if_contradictory_hints`.

        Warning:
            This mapping includes values derived from policy tags.  A tag
            chosen to drive local permission rules (``ALLOW_READONLY``) or a
            deployment profile therefore appears here as a client-facing
            claim.  Transports that publish hints should use
            :attr:`declared_execution_hints` unless the operator explicitly
            opts in to tag-derived claims.

        Returns:
            Mapping of hint name to boolean value; empty when nothing is
            set.
        """
        hints: dict[str, bool] = {}

        read_only = self.read_only_hint
        if read_only is None and ToolTag.READ_ONLY in self.tags:
            read_only = True
        if read_only is not None:
            hints["read_only_hint"] = read_only

        destructive = self.destructive_hint
        if destructive is None and ToolTag.DESTRUCTIVE in self.tags:
            destructive = True
        if destructive is None and read_only:
            # MCP defaults ``destructiveHint`` to true, so a read-only tool
            # that left it unset would ship readOnlyHint=true next to
            # destructiveHint=true.  Fill the unset case with False; an
            # explicit value (or a DESTRUCTIVE tag) still wins.
            destructive = False
        if destructive is not None:
            hints["destructive_hint"] = destructive

        if self.idempotent_hint is not None:
            hints["idempotent_hint"] = self.idempotent_hint
        if self.open_world_hint is not None:
            hints["open_world_hint"] = self.open_world_hint
        return hints

    @property
    def declared_execution_hints(self) -> dict[str, bool]:
        """Execution hints built only from explicit declarations.

        Unlike :attr:`execution_hints`, this never derives a hint from a
        :class:`ToolTag`.  A tool tagged ``READ_ONLY`` for permission policy
        but with no explicit ``read_only_hint`` returns an empty mapping, so a
        transport can publish "no claim" (absent annotations) instead of
        either guessing or asserting a value nobody checked.

        The one complement kept is ``destructive_hint=False`` when
        ``read_only_hint`` was explicitly declared ``True``.  That follows
        from a claim the caller made, not from a tag, and avoids shipping
        ``readOnlyHint=true`` next to the protocol default
        ``destructiveHint=true``.

        Returns:
            Mapping of hint name to explicitly declared boolean; empty when
            nothing was declared.
        """
        hints: dict[str, bool] = {}
        if self.read_only_hint is not None:
            hints["read_only_hint"] = self.read_only_hint
        if self.destructive_hint is not None:
            hints["destructive_hint"] = self.destructive_hint
        elif self.read_only_hint is True:
            # MCP defaults ``destructiveHint`` to true; the complement is
            # implied by an explicit read-only claim.
            hints["destructive_hint"] = False
        if self.idempotent_hint is not None:
            hints["idempotent_hint"] = self.idempotent_hint
        if self.open_world_hint is not None:
            hints["open_world_hint"] = self.open_world_hint
        return hints

    def _warn_if_contradictory_hints(self) -> None:
        """Warn when a tool declares itself both read-only and destructive.

        The two MCP hints are independent, so resolving both to ``True`` is
        not protocol-illegal, but a host that trusts ``readOnlyHint`` to
        skip a confirmation prompt would also skip it for a tool that
        declares itself destructive.

        Called once per metadata instance from :meth:`__post_init__`, which
        is the single choke point for both direct construction and every
        ``dataclasses.replace``-based mutation (runtime updates,
        ``apply_metadata_config``, ``model_copy``).  Reading
        :attr:`execution_hints` never warns.
        """
        hints = self.execution_hints
        if hints.get("read_only_hint") and hints.get("destructive_hint"):
            warnings.warn(
                "ToolMetadata resolves both read_only_hint=True and "
                "destructive_hint=True. These MCP hints are independent and "
                "neither overrides the other, but a host that trusts "
                "readOnlyHint to skip a confirmation prompt may skip it for a "
                "destructive tool.",
                UserWarning,
                stacklevel=2,
            )

    def model_dump(self) -> dict[str, Any]:
        """Serialize to dict. Backward-compatible alias."""
        return dataclasses.asdict(self)

    def model_copy(self, *, update: dict[str, Any] | None = None) -> "ToolMetadata":
        """Clone with optional field overrides. Backward-compatible alias."""
        return dataclasses.replace(self, **(update or {}))


# Override frozen=True auto-generated __hash__ to keep ToolMetadata
# explicitly unhashable, consistent with pre-frozen behavior.
ToolMetadata.__hash__ = None  # type: ignore[assignment]  # ty: ignore[invalid-assignment]


@dataclass(frozen=True, init=False)
class Tool:
    """Base class representing an executable tool/function.

    Provides core functionality for:
        - Function wrapping and metadata management
        - Parameter validation
        - Synchronous/asynchronous execution
        - JSON schema generation

    Note:
        Frozen semantics are shallow — field reassignment is prevented
        but mutable containers (``parameters`` dict, ``metadata.tags``
        set) can still be modified in place.  Mutation should only occur
        during ``__init__``.
    """

    name: str
    """The name of the tool.

    Used as the primary identifier when calling the tool.
    Must be unique within a tool registry.
    """

    description: str
    """Detailed description of the tool's functionality.

    Should clearly explain what the tool does, its purpose,
    and any important usage considerations.
    """

    parameters: dict[str, Any]
    """Parameter schema defining the tool's expected inputs.

    Follows JSON Schema format. Automatically generated from
    the wrapped function's type hints when using from_function().
    """

    callable: Callable[..., Any]
    """The tool's callable, always a :class:`BaseToolWrapper` at runtime.

    Use ``call_sync()`` / ``call_async()`` for sync/async transparent
    execution.
    """

    metadata: ToolMetadata
    """Behavioral and classification metadata for this tool.

    Contains execution hints (``is_async``, ``is_concurrency_safe``,
    ``timeout``) and classification tags (``tags``, ``custom_tags``).
    """

    parameters_model: Any | None
    """Type used for parameter validation.

    Automatically generated from the wrapped function's type hints
    when using from_function(). Can be None for tools without
    parameter validation.
    """

    namespace: str | None
    """The namespace this tool belongs to.

    Used to group tools logically and avoid name collisions.
    When set, the tool's ``name`` is typically prefixed as
    ``{namespace}-{method_name}``.  This field stores the
    *original* namespace string (after normalization) so that
    downstream code can reliably determine group membership
    without parsing the ``name`` field.
    """

    method_name: str | None
    """The original method/function name before namespace prefixing.

    Preserved so that the base name can be recovered without
    ambiguity even when the ``name`` field contains a namespace
    prefix joined by ``-`` (which ``normalize_tool_name`` would
    otherwise convert to ``_``).
    """

    def __init__(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        callable: Callable[..., Any],
        metadata: ToolMetadata | None = None,
        parameters_model: Any | None = None,
        namespace: str | None = None,
        method_name: str | None = None,
        is_async: bool | None = None,
    ) -> None:
        # NOTE: dataclasses.replace() re-runs __init__ on every copy.
        # _normalize_parameters and schema_hash computation are
        # idempotent, so this is safe but does redundant work.
        if metadata is None:
            metadata = (
                ToolMetadata(is_async=is_async)
                if is_async is not None
                else ToolMetadata()
            )
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "parameters", self._normalize_parameters(parameters))
        object.__setattr__(self, "callable", callable)
        object.__setattr__(self, "parameters_model", parameters_model)
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "method_name", method_name)
        if not metadata.schema_hash:
            metadata = dataclasses.replace(
                metadata, schema_hash=compute_schema_hash(self.parameters)
            )
        object.__setattr__(self, "metadata", metadata)

    def __getstate__(self) -> dict[str, Any]:
        """Avoid pickling the dynamically created TypedDict on Python 3.11+."""
        state = self.__dict__.copy()
        model = self.parameters_model
        if (
            isinstance(self.callable, _FunctionToolWrapper)
            and isinstance(model, type)
            and model.__module__ == "toolregistry._vendor.validate"
        ):
            state["parameters_model"] = None
            state["_rebuild_parameters_model"] = True
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore native parameter validation after deserialization.

        Regeneration can fail for annotations that no longer resolve in the
        loading process (local classes, optional dependencies).  The tool is
        then restored without parameter validation and a ``UserWarning``
        says so, matching ``Tool.from_function``.  With warnings escalated
        to errors (``python -W error``) that warning raises and the tool
        still fails to load.
        """
        rebuild = state.pop("_rebuild_parameters_model", False)
        for key, value in state.items():
            object.__setattr__(self, key, value)
        if rebuild and isinstance(self.callable, _FunctionToolWrapper):
            try:
                model = _generate_parameters_model(self.callable.fn)
            except Exception as e:  # pragma: no cover - exotic annotations
                warnings.warn(
                    f"Failed to regenerate parameter model for "
                    f"'{self.name}' after unpickling: {e}. "
                    "The tool will be usable without parameter validation.",
                    UserWarning,
                    stacklevel=2,
                )
                model = None
            object.__setattr__(self, "parameters_model", model)

    @classmethod
    def _normalize_parameters(cls, parameters: dict[str, Any]) -> dict[str, Any]:
        """Normalize and flatten a parameter schema at construction time.

        Ensures the schema is {type: object, properties: {...}},
        then runs flatten_schema to resolve $ref, merge
        allOf, simplify anyOf/oneOf, and strip unsupported
        keywords.  The result is a clean, wire-safe JSON Schema that
        faithfully represents the function signature.
        """
        from ._vendor.jsonschema import flatten_schema

        if parameters.get("type") != "object":
            parameters = {"type": "object", "properties": {}}
        elif not isinstance(parameters.get("properties"), dict):
            parameters = {**parameters, "properties": {}}

        return flatten_schema(parameters, strip_keys=cls._EXTRA_STRIP_KEYS)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict, excluding non-serializable fields."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "metadata": dataclasses.asdict(self.metadata),
            "namespace": self.namespace,
            "method_name": self.method_name,
        }

    def model_dump(self) -> dict[str, Any]:
        """Backward-compatible alias for :meth:`to_dict`."""
        return self.to_dict()

    @property
    def is_async(self) -> bool:
        """Whether the tool requires async execution.

        Backward-compatible proxy to ``metadata.is_async``.
        """
        return self.metadata.is_async

    @property
    def execution_hints(self) -> dict[str, bool]:
        """Resolved execution hints from :attr:`metadata`.

        Convenience proxy to ``metadata.execution_hints``; see
        :attr:`ToolMetadata.execution_hints` for the tri-state contract
        and tag-derivation rule.  ``title`` is not part of this mapping;
        read :attr:`ToolMetadata.title` for the display name.
        """
        return self.metadata.execution_hints

    @property
    def declared_execution_hints(self) -> dict[str, bool]:
        """Explicitly declared execution hints, excluding tag-derived values.

        Convenience proxy to :attr:`ToolMetadata.declared_execution_hints`;
        transports should publish this mapping rather than the resolved one.
        """
        return self.metadata.declared_execution_hints

    @property
    def fn(self) -> Callable[..., Any]:
        """Return the underlying unwrapped function.

        For native tools (registered via ``from_function``), returns the
        original Python function.  For integration tools (MCP, OpenAPI,
        LangChain), returns the wrapper itself.
        """
        if isinstance(self.callable, _FunctionToolWrapper):
            return self.callable.fn
        return self.callable

    @property
    def qualified_name(self) -> str:
        """Return the fully-qualified tool name.

        ``name`` is authoritative: registration and every namespace operation
        rebuild it from ``namespace``, ``method_name`` and the registry
        separator (see :meth:`requalify`).  The property therefore simply
        exposes ``name``.

        Returns:
            str: The qualified name of the tool.
        """
        return self.name

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
        namespace: str | None = None,
        method_name: str | None = None,
        metadata: ToolMetadata | None = None,
        sep: NameSeparator = "-",
    ) -> "Tool":
        """Factory method to create Tool from callable.

        Automatically:
            - Extracts function metadata
            - Generates parameter schema
            - Handles async/sync detection

        Args:
            func: Function to convert to tool.
            name: Override tool name (defaults to function name).
            description: Override description (defaults to docstring).
            namespace: Namespace the tool belongs to.
            method_name: Original method name of the tool.
            metadata: Optional ToolMetadata; ``is_async`` is always
                auto-detected and will override the value in *metadata*.
            sep: Separator between *namespace* and the tool name.  Pass the
                registry's ``name_sep`` so the resulting name matches the
                registry key.

        Returns:
            Tool: Configured Tool instance.

        Raises:
            ValueError: For unnamed lambda functions.
        """
        func_name = name or getattr(func, "__name__", "<unknown>")

        if func_name == "<lambda>":
            raise ValueError("You must provide a name for lambda functions")

        func_name = normalize_tool_name(func_name)

        # Determine the method_name: use provided value, or fall back to
        # the normalized function name (before namespace prefixing).
        resolved_method_name = method_name or func_name

        func_doc = description or func.__doc__ or ""
        is_async = inspect.iscoroutinefunction(func)

        # Build metadata: start from caller-supplied or default, then
        # force is_async to the auto-detected value.
        if metadata is None:
            metadata = ToolMetadata(is_async=is_async)
        else:
            metadata = dataclasses.replace(metadata, is_async=is_async)

        parameters_model = None
        try:
            parameters_model = _generate_parameters_model(func)
        except Exception as e:
            warnings.warn(
                f"Failed to generate parameter model for '{func_name}': {e}. "
                "The tool will be registered without parameter validation.",
                UserWarning,
                stacklevel=2,
            )
            parameters_model = None
        if parameters_model is not None:
            from ._vendor.validate import json_schema as _json_schema

            schema = _json_schema(parameters_model)
            if getattr(parameters_model, "_has_var_keyword", False):
                schema["additionalProperties"] = True
            schema = _normalize_union_keywords(schema)
            parameters_schema = _simplify_nullable_schemas(schema)
        else:
            parameters_schema = {}
        # Wrap bare functions so Tool.callable is always a BaseToolWrapper.
        if not isinstance(func, BaseToolWrapper):
            param_names = list(inspect.signature(func).parameters.keys())
            wrapper = _FunctionToolWrapper(fn=func, name=func_name, params=param_names)
        else:
            wrapper = func

        tool = cls(
            name=func_name,
            description=func_doc,
            parameters=parameters_schema,
            callable=wrapper,
            metadata=metadata,
            parameters_model=parameters_model if parameters_model is not None else None,
            method_name=resolved_method_name,
        )

        if namespace:
            tool = tool.update_namespace(namespace, sep=sep)

        return tool

    #: Schema keys stripped during parameter normalization.
    #: title and nullable are Pydantic v2 artifacts that most LLM
    #: providers either reject or misinterpret.
    _EXTRA_STRIP_KEYS: ClassVar[set[str]] = {"title", "nullable"}

    def get_schema(
        self,
        api_format: API_FORMATS = "openai-chat",
        *,
        _think_augment: bool | None = None,
    ) -> dict[str, Any]:
        """Generate schema representation of tool for a target API format.

        Parameters are already flattened and sanitized at construction
        (see :meth:`_normalize_parameters`).  This method wraps them in
        the target provider format and optionally injects a
        ``toolcall_reason`` property for think-augmented calling.

        Args:
            api_format: Target API format. One of ``"openai-chat"``,
                ``"openai-responses"``, ``"anthropic"``, ``"gemini"``.
            _think_augment: Override for toolcall_reason injection.
                ``True`` → include, ``False``/``None`` → exclude.
                When ``None``, falls back to
                ``self.metadata.think_augment``.  Used by
                :meth:`ToolRegistry.get_schemas` to pass the resolved
                effective value.

        Returns:
            Provider-specific tool definition dict.
        """
        from .llm._rosetta import _make_ir_tool_definition
        from .llm.tool_calls import _get_tool_ops, _normalize_api_format

        api_format = _normalize_api_format(api_format)

        # Resolve effective think_augment: explicit override > per-tool metadata
        effective = (
            _think_augment
            if _think_augment is not None
            else self.metadata.think_augment
        )
        should_include_reason = effective is True

        base_props = self.parameters.get("properties", {})
        if should_include_reason:
            params = {
                **self.parameters,
                "properties": {
                    **base_props,
                    "toolcall_reason": TOOLCALL_REASON_PROPERTY,
                },
            }
        else:
            params = {**self.parameters, "properties": dict(base_props)}

        ir_tool = _make_ir_tool_definition(self.name, self.description, params)

        if api_format == "rosetta-ir":
            return ir_tool

        ops = _get_tool_ops(api_format)
        result = ops.ir_tool_definition_to_p(ir_tool)

        if api_format == "gemini":
            # Unwrap the function_declarations wrapper to return a single
            # tool definition, consistent with other format outputs.
            return result["function_declarations"][0]

        _apply_flattened_parameters(result, params, api_format)
        return result

    def get_json_schema(
        self,
        api_format: API_FORMATS = "openai-chat",
    ) -> dict[str, Any]:
        """Deprecated: use :meth:`get_schema` instead."""
        import warnings

        warnings.warn(
            "get_json_schema() is deprecated, use get_schema() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.get_schema(api_format)

    def describe(
        self,
        api_format: API_FORMATS = "openai-chat",
    ) -> dict[str, Any]:
        """Deprecated: use :meth:`get_schema` instead."""
        import warnings

        warnings.warn(
            "describe() is deprecated, use get_schema() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.get_schema(api_format)

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Validate parameters against tool schema.

        Args:
            parameters: Raw input parameters.

        Returns:
            Validated and normalized parameters.
        """
        if self.parameters_model is None:
            return parameters

        from ._vendor.validate import validate as _validate_fn

        validated = _validate_fn(parameters, self.parameters_model, coerce=True)

        if getattr(self.parameters_model, "_has_var_keyword", False):
            return validated

        declared = set(
            get_type_hints(self.parameters_model, include_extras=True).keys()
        )
        return {k: validated[k] for k in declared if k in validated}

    _validate_parameters = validate_parameters  # backward compat

    def run(self, parameters: dict[str, Any]) -> Any:
        """Execute tool synchronously.

        Delegates to ``callable.call_sync()`` which handles sync/async
        callable transparency.  Exceptions propagate directly.

        Args:
            parameters: Input parameters for the tool.

        Returns:
            The tool execution result.

        Raises:
            Exception: Any exception raised during validation or execution.

        Note:
            Result size truncation (via ``max_result_size``) is only applied
            when tools are executed through
            ``ToolRegistry.execute_tool_calls()``. Direct calls return raw
            results without truncation.
        """
        parameters = {k: v for k, v in parameters.items() if k != "toolcall_reason"}
        validated_params = self.validate_parameters(parameters)
        return self.callable.call_sync(**validated_params)  # ty: ignore[unresolved-attribute]

    async def arun(self, parameters: dict[str, Any]) -> Any:
        """Execute tool asynchronously.

        Delegates to ``callable.call_async()`` which handles sync/async
        callable transparency.  Exceptions propagate directly.

        Args:
            parameters: Input parameters for the tool.

        Returns:
            The tool execution result.

        Raises:
            Exception: Any exception raised during validation or execution.

        Note:
            Result size truncation (via ``max_result_size``) is only applied
            when tools are executed through
            ``ToolRegistry.execute_tool_calls()``. Direct calls return raw
            results without truncation.
        """
        parameters = {k: v for k, v in parameters.items() if k != "toolcall_reason"}
        validated_params = self.validate_parameters(parameters)
        return await self.callable.call_async(**validated_params)  # ty: ignore[unresolved-attribute]

    def run_raw(self, parameters: dict[str, Any]) -> Any:
        """Deprecated alias for ``run()``.

        .. deprecated:: 0.12.0
            Use ``run()`` instead.  ``run_raw`` will be removed in a
            future version.
        """
        warnings.warn(
            "Tool.run_raw() is deprecated; use Tool.run() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.run(parameters)

    async def arun_raw(self, parameters: dict[str, Any]) -> Any:
        """Deprecated alias for ``arun()``.

        .. deprecated:: 0.12.0
            Use ``arun()`` instead.  ``arun_raw`` will be removed in a
            future version.
        """
        warnings.warn(
            "Tool.arun_raw() is deprecated; use Tool.arun() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.arun(parameters)

    def with_refreshed_at(self: _ToolT, timestamp: str) -> _ToolT:
        """Return a copy with ``last_refreshed_at`` updated."""
        return dataclasses.replace(
            self,
            metadata=dataclasses.replace(self.metadata, last_refreshed_at=timestamp),
        )

    def requalify(
        self: _ToolT,
        namespace: str | None,
        sep: NameSeparator = "-",
    ) -> _ToolT:
        """Return a copy whose name is rebuilt from *namespace* and *method_name*.

        ``name`` is derived, never parsed: the unqualified name comes from
        :attr:`method_name` (falling back to the current name for tools built
        before that field existed), then it is recombined with *namespace* using
        *sep*.  Passing ``namespace=None`` drops the namespace and keeps only the
        method name.

        This is the primitive behind ``spinoff``, ``reduce_namespace`` and
        separator conversion during ``merge``.

        Args:
            namespace: Namespace to apply, or ``None`` to flatten.
            sep: Separator between namespace and method name.

        Returns:
            A copy with consistent ``name``, ``namespace`` and ``method_name``.
        """
        method_name = self.method_name or self._method_name_from_name(sep)
        if namespace:
            new_namespace: str | None = normalize_tool_name(namespace)
            new_name = f"{new_namespace}{sep}{method_name}"
        else:
            new_namespace = None
            new_name = method_name

        return dataclasses.replace(
            self,
            name=new_name,
            namespace=new_namespace,
            method_name=method_name,
        )

    def _method_name_from_name(self, sep: NameSeparator) -> str:
        """Recover the unqualified method name from ``name``.

        Prefers the namespace boundary, then either supported separator.  Only
        used for tools built without ``method_name``.  Names created through
        registration are normalized, so any separator in them is a namespace
        boundary; a hand-built tool whose literal name contains ``-`` or ``.``
        has no way to distinguish the two and will be split at the first one.
        """
        if self.namespace:
            for boundary in (
                f"{self.namespace}{sep}",
                f"{self.namespace}-",
                f"{self.namespace}.",
            ):
                if self.name.startswith(boundary):
                    return self.name[len(boundary) :]
        for boundary_sep in ("-", "."):
            if boundary_sep in self.name:
                return self.name.split(boundary_sep, 1)[1]
        return self.name

    def update_namespace(
        self: _ToolT,
        namespace: str | None,
        force: bool = False,
        sep: NameSeparator = "-",
    ) -> _ToolT:
        """Return a copy of the tool with an updated namespace.

        Names are always derived from ``namespace``, ``method_name`` and *sep*;
        the tool is never renamed by parsing its current name.  OpenAI requires
        function names to match ``^[a-zA-Z0-9_-]+$``; some other providers allow
        dot (``.``) as separator.

        If a namespace prefix already exists and *force* is ``True``, the
        existing namespace is replaced.  If *force* is ``False``, a tool that is
        already qualified is returned unchanged (both ``name`` and
        ``namespace`` are preserved).  A name containing either ``-`` or ``.``
        counts as already qualified; registration normalizes separators away, so
        this heuristic only affects hand-built ``Tool`` instances.  If no
        namespace exists, the new *namespace* is applied.

        Args:
            namespace: The new namespace to apply to the tool's name.
            force: If ``True``, forces the replacement of an existing
                namespace.  Defaults to ``False``.
            sep: Separator character between namespace and method name.

        Returns:
            A new ``Tool`` instance with the updated namespace.  Returns
            ``self`` unchanged when *namespace* is falsy or when *force* is
            ``False`` and the tool is already qualified.

        Example:
            ```python
            tool = Tool(name="example_tool", ...)
            tool = tool.update_namespace("new_namespace")
            tool.name  # 'new_namespace-example_tool'

            tool = Tool(name="old_namespace-example_tool", ...)
            tool = tool.update_namespace("new_namespace", force=False)
            tool.name  # 'old_namespace-example_tool'

            tool = Tool(name="old_namespace.example_tool", ...)
            tool = tool.update_namespace("new_namespace", force=True, sep=".")
            tool.name  # 'new_namespace.example_tool'
            ```
        """
        if not namespace:
            return self
        if not force and (self.namespace or any(s in self.name for s in ("-", "."))):
            return self

        new_name, new_method_name = qualify_name(
            self.name,
            namespace,
            sep,
            force=force,
            method_name=self.method_name,
        )

        return dataclasses.replace(
            self,
            name=new_name,
            namespace=normalize_tool_name(namespace),
            method_name=new_method_name,
        )


# Override frozen=True auto-generated __hash__ to keep Tool
# explicitly unhashable, consistent with pre-frozen behavior.
Tool.__hash__ = None  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
