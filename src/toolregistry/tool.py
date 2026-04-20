import inspect
import warnings
from enum import Enum
from typing import Any, Literal
from collections.abc import Callable

from pydantic import BaseModel, Field, model_validator

from .parameter_models import _generate_parameters_model
from .types import API_FORMATS
from .utils import normalize_tool_name


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


THINK_PROPERTY: dict[str, str] = {
    "type": "string",
    "description": (
        "Your step-by-step reasoning about why you chose this tool and how to use it."
    ),
}
"""Schema snippet injected into every tool's ``parameters.properties``
so that LLMs can include chain-of-thought reasoning when calling a tool.

Reference: https://arxiv.org/abs/2601.18282
"""


class ToolMetadata(BaseModel):
    """Behavioral and classification metadata for a Tool.

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
        extra: Arbitrary key-value pairs for application-specific use.
    """

    is_async: bool = False
    is_concurrency_safe: bool = True
    timeout: float | None = None
    locality: Literal["local", "remote", "any"] = "any"
    max_result_size: int | None = None

    tags: set[ToolTag] = Field(default_factory=set)
    custom_tags: set[str] = Field(default_factory=set)

    extra: dict[str, Any] = Field(default_factory=dict)

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
    - ``True``: always inject a ``thought`` property into this tool's
      schema, regardless of the registry setting.
    - ``False``: never inject ``thought`` into this tool's schema.

    Reference: https://arxiv.org/abs/2601.18282
    """

    @property
    def all_tags(self) -> set[str]:
        """Union of predefined and custom tags (all as str)."""
        return {t.value for t in self.tags} | self.custom_tags


class Tool(BaseModel):
    """Base class representing an executable tool/function.

    Provides core functionality for:
        - Function wrapping and metadata management
        - Parameter validation using Pydantic
        - Synchronous/asynchronous execution
        - JSON schema generation
    """

    name: str = Field(description="Name of the tool")
    """The name of the tool.
    
    Used as the primary identifier when calling the tool.
    Must be unique within a tool registry.
    """

    description: str = Field(description="Description of what the tool does")
    """Detailed description of the tool's functionality.
    
    Should clearly explain what the tool does, its purpose,
    and any important usage considerations.
    """

    parameters: dict[str, Any] = Field(description="JSON schema for tool parameters")
    """Parameter schema defining the tool's expected inputs.
    
    Follows JSON Schema format. Automatically generated from
    the wrapped function's type hints when using from_function().
    """

    callable: Callable[..., Any] = Field(exclude=True)
    """The underlying function/method that implements the tool's logic.

    This is excluded from serialization to prevent accidental exposure
    of sensitive implementation details.
    """

    metadata: ToolMetadata = Field(default_factory=ToolMetadata)
    """Behavioral and classification metadata for this tool.

    Contains execution hints (``is_async``, ``is_concurrency_safe``,
    ``timeout``) and classification tags (``tags``, ``custom_tags``).
    """

    parameters_model: Any | None = Field(
        default=None, description="Pydantic Model for tool parameters"
    )
    """Pydantic model used for parameter validation.
    
    Automatically generated from the wrapped function's type hints
    when using from_function(). Can be None for tools without
    parameter validation.
    """

    namespace: str | None = Field(
        default=None, description="Namespace the tool belongs to"
    )
    """The namespace this tool belongs to.

    Used to group tools logically and avoid name collisions.
    When set, the tool's ``name`` is typically prefixed as
    ``{namespace}-{method_name}``.  This field stores the
    *original* namespace string (after normalization) so that
    downstream code can reliably determine group membership
    without parsing the ``name`` field.
    """

    method_name: str | None = Field(
        default=None, description="Original method name of the tool"
    )
    """The original method/function name before namespace prefixing.

    Preserved so that the base name can be recovered without
    ambiguity even when the ``name`` field contains a namespace
    prefix joined by ``-`` (which ``normalize_tool_name`` would
    otherwise convert to ``_``).
    """

    @model_validator(mode="before")
    @classmethod
    def _migrate_is_async(cls, data: Any) -> Any:
        """Accept legacy ``is_async`` constructor kwarg and move it into metadata."""
        if isinstance(data, dict) and "is_async" in data:
            is_async = data.pop("is_async")
            if "metadata" not in data:
                data["metadata"] = ToolMetadata(is_async=is_async)
            elif isinstance(data["metadata"], dict):
                data["metadata"].setdefault("is_async", is_async)
        return data

    def model_post_init(self, __context: Any) -> None:
        """Inject ``thought`` property into the tool's parameter schema.

        Runs after every ``Tool`` (and subclass) construction, regardless
        of whether the instance was created via ``from_function()``, or
        directly (MCP, OpenAPI, LangChain integrations).

        The ``thought`` field is only added when ``parameters`` already
        contains a ``properties`` mapping and does not already define a
        ``thought`` key (i.e. native ``thought`` parameters are preserved).
        """
        props = self.parameters.get("properties")
        if props is not None and "thought" not in props:
            props["thought"] = THINK_PROPERTY

    def _has_native_thought_param(self) -> bool:
        """Return True if the wrapped function natively declares a ``thought`` parameter."""
        return (
            self.parameters_model is not None
            and "thought" in self.parameters_model.model_fields
        )

    @property
    def is_async(self) -> bool:
        """Whether the tool requires async execution.

        Backward-compatible proxy to ``metadata.is_async``.
        """
        return self.metadata.is_async

    @property
    def qualified_name(self) -> str:
        """Return the fully-qualified tool name.

        If a ``namespace`` is set, returns ``{namespace}-{method_name}``.
        Otherwise falls back to the ``name`` field.

        Returns:
            str: The qualified name of the tool.
        """
        if self.namespace and self.method_name:
            return f"{self.namespace}-{self.method_name}"
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
            metadata = metadata.model_copy(update={"is_async": is_async})

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
        parameters_schema = (
            parameters_model.model_json_schema() if parameters_model else {}
        )
        tool = cls(
            name=func_name,
            description=func_doc,
            parameters=parameters_schema,
            callable=func,
            metadata=metadata,
            parameters_model=parameters_model if parameters_model is not None else None,
            method_name=resolved_method_name,
        )

        if namespace:
            tool.update_namespace(namespace)

        return tool

    def _parameters_without_thought(self) -> dict[str, Any]:
        """Return a shallow copy of ``parameters`` with ``thought`` removed.

        Only strips ``thought`` when it was injected (i.e. the wrapped
        function does not natively declare a ``thought`` parameter).
        """
        import copy

        if self._has_native_thought_param():
            return self.parameters
        params = copy.deepcopy(self.parameters)
        props = params.get("properties")
        if props is not None:
            props.pop("thought", None)
        return params

    def get_schema(
        self,
        api_format: API_FORMATS = "openai-chat",
        *,
        _think_augment: bool | None = None,
    ) -> dict[str, Any]:
        """Generate schema representation of tool for a target API format.

        All formats are produced via llm-rosetta converters, which also
        apply schema sanitization (stripping unsupported JSON Schema
        keywords like ``$ref``, ``$schema``, ``anyOf``, etc.).

        Args:
            api_format: Target API format. One of ``"openai-chat"``,
                ``"openai-response"``, ``"anthropic"``, ``"gemini"``.
            _think_augment: Internal override for thought injection.
                When ``None`` (default), falls back to
                ``self.metadata.think_augment``.  Used by
                :meth:`ToolRegistry.get_schemas` to pass the resolved
                effective value.

        Returns:
            Provider-specific tool definition dict.
        """
        from ._rosetta import _make_ir_tool_definition
        from .types.common import _normalize_api_format

        api_format = _normalize_api_format(api_format)

        # Resolve effective think_augment: explicit override > per-tool metadata
        effective = (
            _think_augment
            if _think_augment is not None
            else self.metadata.think_augment
        )
        # None means "include" when called directly (no registry context)
        should_include_thought = effective is not False

        params = (
            self.parameters
            if should_include_thought
            else self._parameters_without_thought()
        )
        ir_tool = _make_ir_tool_definition(self.name, self.description, params)

        if api_format == "openai-chat":
            from ._rosetta import _get_openai_chat_tool_ops

            return _get_openai_chat_tool_ops().ir_tool_definition_to_p(ir_tool)
        elif api_format == "openai-response":
            from ._rosetta import _get_openai_responses_tool_ops

            return _get_openai_responses_tool_ops().ir_tool_definition_to_p(ir_tool)
        elif api_format == "anthropic":
            from ._rosetta import _get_anthropic_tool_ops

            return _get_anthropic_tool_ops().ir_tool_definition_to_p(ir_tool)
        elif api_format == "gemini":
            from ._rosetta import _get_google_tool_ops

            result = _get_google_tool_ops().ir_tool_definition_to_p(ir_tool)
            # Unwrap the function_declarations wrapper to return a single
            # tool definition, consistent with other format outputs.
            return result["function_declarations"][0]
        else:
            raise ValueError(f"Unsupported API format: {api_format}")

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

    def _validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Validate parameters against tool schema.

        Uses Pydantic model if available, otherwise performs basic validation.

        Args:
            parameters (Dict[str, Any]): Raw input parameters.

        Returns:
            Dict[str, Any]: Validated and normalized parameters.
        """
        if self.parameters_model is None:
            validated_params = parameters
        else:
            model = self.parameters_model(**parameters)
            validated_params = model.model_dump_one_level()
        return validated_params

    def run(self, parameters: dict[str, Any]) -> Any:
        """Execute tool synchronously.

        Args:
            parameters (Dict[str, Any]): Validated input parameters.

        Returns:
            Any: Tool execution result.

        Raises:
            Exception: On execution failure.

        Note:
            Result size truncation (via ``max_result_size``) is only applied
            when tools are executed through
            ``ToolRegistry.execute_tool_calls()``. Direct calls to ``run()``
            return raw results without truncation.
        """
        try:
            if not self._has_native_thought_param():
                parameters = {k: v for k, v in parameters.items() if k != "thought"}
            validated_params = self._validate_parameters(parameters)
            return self.callable(**validated_params)
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"

    async def arun(self, parameters: dict[str, Any]) -> Any:
        """Execute tool asynchronously.

        Args:
            parameters (Dict[str, Any]): Validated input parameters.

        Returns:
            Any: Tool execution result.

        Raises:
            NotImplementedError: If async execution unsupported.
            Exception: On execution failure.

        Note:
            Result size truncation (via ``max_result_size``) is only applied
            when tools are executed through
            ``ToolRegistry.execute_tool_calls()``. Direct calls to ``arun()``
            return raw results without truncation.
        """
        try:
            if not self._has_native_thought_param():
                parameters = {k: v for k, v in parameters.items() if k != "thought"}
            validated_params = self._validate_parameters(parameters)

            if inspect.iscoroutinefunction(self.callable):
                return await self.callable(**validated_params)
            elif hasattr(self.callable, "__call__"):
                return await self.callable(**validated_params)
            raise NotImplementedError(
                "Async execution requires either an async function (coroutine) "
                "or a callable whose __call__ method is async or returns an awaitable object."
            )
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"

    def update_namespace(
        self,
        namespace: str | None,
        force: bool = False,
        sep: Literal["-", "."] = "-",
    ) -> None:
        """Updates the namespace of a tool.

        This method checks if the tool's name already contains a namespace (indicated by the presence of a separator character).
        OpenAI requires that function names match the pattern ``^[a-zA-Z0-9_-]+$``. Some other providers allow dot (`.`) as separator.
        If it does and `force` is `True`, the existing namespace is replaced with the provided `namespace`.
        If `force` is `False` and an existing namespace is present, no changes are made.
        If the tool's name does not contain a namespace, the `namespace` is prepended as a prefix to the tool's name.

        Args:
            namespace (str): The new namespace to apply to the tool's name.
            force (bool, optional): If `True`, forces the replacement of an existing namespace. Defaults to `False`.

        Returns:
            None: This method modifies the `tool.name` attribute in place and does not return a value.

        Example:
            ```python
            tool = Tool(name="example_tool")
            tool.update_namespace("new_namespace")
            tool.name  # 'new_namespace-example_tool'

            tool = Tool(name="old_namespace.example_tool")
            tool.update_namespace("new_namespace", force=False)
            tool.name  # 'old_namespace-example_tool'

            tool = Tool(name="old_namespace.example_tool")
            tool.update_namespace("new_namespace", force=True, sep=".")
            tool.name  # 'new_namespace.example_tool'
            ```
        """
        if not namespace:
            return

        namespace = normalize_tool_name(namespace)

        # Ensure method_name is populated before updating the name.
        # If method_name was never set, derive it from the current name
        # (stripping any existing namespace prefix).
        if not self.method_name:
            if sep in self.name:
                self.method_name = self.name.split(sep, 1)[1]
            else:
                self.method_name = self.name

        self.namespace = namespace

        if sep in self.name:
            if force:
                # Replace existing namespace with the new one if force is True
                self.name = f"{namespace}{sep}{self.name.split(sep, 1)[1]}"
            else:
                # Do not change the name if force is False and an existing namespace is present
                pass
        else:
            # Add the new namespace as a prefix if there is no existing namespace
            self.name = f"{namespace}{sep}{self.name}"
