"""Structural integration for LangChain-style tools.

The integration is deliberately dependency-free: it accepts any object that
looks like a ``langchain_core.tools.BaseTool`` (``name``, ``description``, a
schema source, and a sync/async runner).  ``langchain-core`` is not imported, so
tools from partner packages, community packages, or plain Python objects all
work without installing LangChain.

Schema sources are tried in this order:

1. ``input_schema`` — a pydantic model (or an object with
   ``model_json_schema()`` / pydantic-v1 ``schema()``) or a JSON-schema dict.
2. ``args_schema`` — same forms.
3. ``parameters`` — a JSON-schema dict.
4. ``args`` — a ``{name: property_schema}`` dict, wrapped in an object schema.

Runners are tried in this order: sync ``_run`` / ``run`` / ``func``; async
``_arun`` / ``arun`` / ``coroutine``.  A sync-only tool still serves ``arun``
through a worker thread.  The reverse is not symmetric: a duck-typed object
that exposes only an async runner is registered with ``is_async=False`` and
must be called through ``ainvoke()``; ``invoke()`` raises a clear error.
"""

import asyncio
from typing import Any

from ..._vendor.structlog import get_logger
from ..._names import NameSeparator, qualified_tool_name
from ...tool import Tool, ToolMetadata
from ...tool_registry import ToolRegistry
from ...tool_wrapper import BaseToolWrapper
from ...utils import ToolNameFilter, normalize_tool_name

logger = get_logger()


def _tool_name(tool: Any) -> str:
    """Return the tool's advertised name, raising a clear error otherwise."""
    name = getattr(tool, "name", None)
    if not isinstance(name, str) or not name:
        raise TypeError(
            "LangChain-style tool must expose a non-empty string 'name' "
            f"attribute; got {type(tool).__name__}."
        )
    return name


def _extract_input_schema(tool: Any) -> dict[str, Any]:
    """Return a JSON-schema dict for *tool*'s parameters.

    See the module docstring for the source order.  The returned dict is a
    fresh copy when the source is a dict, so callers may mutate it.

    Raises:
        TypeError: If the tool exposes no usable schema source.
    """
    for attr in ("input_schema", "args_schema"):
        schema = getattr(tool, attr, None)
        if schema is None:
            continue
        model_json_schema = getattr(schema, "model_json_schema", None)
        if callable(model_json_schema):
            return dict(model_json_schema())
        # pydantic v1 models expose ``schema()`` instead; skipping it would
        # silently drop ``required`` and fall through to ``tool.args``.
        legacy_schema = getattr(schema, "schema", None)
        if callable(legacy_schema):
            return dict(legacy_schema())
        if isinstance(schema, dict):
            return dict(schema)

    parameters = getattr(tool, "parameters", None)
    if isinstance(parameters, dict):
        return dict(parameters)

    args = getattr(tool, "args", None)
    if isinstance(args, dict):
        return {"type": "object", "properties": dict(args)}

    raise TypeError(
        f"LangChain-style tool {_tool_name(tool)!r} exposes no parameter schema: "
        "expected input_schema/args_schema (pydantic model or dict), a "
        "'parameters' dict, or an 'args' dict."
    )


def _extract_params(tool: Any, schema: dict[str, Any]) -> list[str]:
    """Return parameter names, preferring ``tool.args`` when present."""
    args = getattr(tool, "args", None)
    if isinstance(args, dict) and args:
        return [str(key) for key in args]
    properties = schema.get("properties")
    return [str(key) for key in properties] if isinstance(properties, dict) else []


def _resolve_runner(tool: Any, attributes: tuple[str, ...]) -> Any:
    """Return the first callable runner among *attributes*, else ``None``."""
    for attr in attributes:
        runner = getattr(tool, attr, None)
        if callable(runner):
            return runner
    return None


class LangChainToolWrapper(BaseToolWrapper):
    """Wrapper providing sync and async entry points for a LangChain-style tool.

    Attributes:
        tool (Any): The wrapped object.
        name (str): Normalized tool name.
        params (list[str]): Parameter names.
    """

    def __init__(self, tool: Any) -> None:
        """Initialize the wrapper.

        Args:
            tool: Object exposing ``name``, ``description`` and a schema source.
        """
        schema = _extract_input_schema(tool)
        super().__init__(
            name=normalize_tool_name(_tool_name(tool)),
            params=_extract_params(tool, schema),
        )
        self.tool = tool
        # Kept so callers can reuse the extracted schema instead of walking
        # the source attributes a second time.
        self.input_schema = schema

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Run the tool synchronously.

        Args:
            args: Positional arguments.
            kwargs: Keyword arguments.

        Returns:
            The tool's return value.

        Raises:
            TypeError: If the tool exposes no sync runner.
            Exception: Whatever the tool raises.
        """
        runner = _resolve_runner(self.tool, ("_run", "run", "func"))
        if runner is None:
            raise TypeError(
                f"LangChain-style tool {self.name!r} exposes no sync runner "
                "('_run', 'run', or 'func')."
            )
        try:
            return runner(*args, **kwargs)
        except Exception:
            import traceback

            logger.error(
                f"Original Exception happens at {self.name}:\n{traceback.format_exc()}"
            )
            raise  # throw to keep the original behavior

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Run the tool asynchronously.

        Uses the tool's async runner when available; otherwise the sync runner
        runs in a worker thread so the event loop is not blocked.

        Args:
            args: Positional arguments.
            kwargs: Keyword arguments.

        Returns:
            The tool's return value.

        Raises:
            Exception: Whatever the tool raises.
        """
        runner = _resolve_runner(self.tool, ("_arun", "arun", "coroutine"))
        try:
            if runner is not None:
                try:
                    return await runner(*args, **kwargs)
                except NotImplementedError:
                    # BaseTool's default ``_arun`` raises this for sync-only
                    # tools; fall through to the thread path.
                    pass
            return await asyncio.to_thread(self.call_sync, *args, **kwargs)
        except Exception:
            import traceback

            logger.error(
                f"Original Exception happens at {self.name}:\n{traceback.format_exc()}"
            )
            raise  # throw to keep the original behavior


class LangChainTool(Tool):
    """Wrapper class for LangChain-style tools that preserves tool metadata."""

    @classmethod
    def from_langchain_tool(
        cls,
        tool: Any,
        namespace: str | None = None,
        sep: NameSeparator = "-",
    ) -> "LangChainTool":
        """Create a LangChainTool from a LangChain-style object.

        Args:
            tool: Object exposing ``name``, ``description`` and a schema source.
            namespace: Optional namespace to prefix the tool name.
            sep: Separator between namespace and tool name.  Pass the
                registry's ``name_sep`` so the stored key matches.

        Returns:
            LangChainTool: A new instance.

        Raises:
            TypeError: If the tool exposes no name or no usable schema.
        """
        wrapper = LangChainToolWrapper(tool)
        # Reuse the schema the wrapper already extracted.
        input_schema = dict(wrapper.input_schema)
        # Drop the auto-generated top-level description for consistency.  It is
        # absent when the args model has no docstring, on any core version.
        input_schema.pop("description", None)

        # Use the fully-qualified class name as source_detail.
        tool_cls = type(tool)
        source_detail = f"{tool_cls.__module__}.{tool_cls.__qualname__}"

        tool_instance = cls(
            name=wrapper.name,
            description=getattr(tool, "description", "") or "",
            parameters=input_schema,
            callable=wrapper,
            metadata=ToolMetadata(
                is_async=False,
                source="langchain",
                source_detail=source_detail,
            ),
        )

        if namespace:
            tool_instance = tool_instance.update_namespace(namespace, sep=sep)

        return tool_instance


class LangChainIntegration:
    """Handles registration of LangChain-style tools.

    Attributes:
        registry (ToolRegistry): Tool registry instance.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def register_langchain_tools_async(
        self,
        tool: Any,
        namespace: bool | str = False,
        include: str | list[str] | None = None,
        exclude: str | list[str] | None = None,
        allow_replace: bool = False,
    ) -> None:
        """Register a LangChain-style tool from an async caller.

        Construction is fast and CPU-bound, so it runs inline rather than
        borrowing the event loop's default executor.  (Other integrations still
        use ``run_in_executor(None, ...)``; see #311 for that class of leak.)

        Args:
            tool: Object exposing ``name``, ``description`` and a schema source.
            namespace (Union[bool, str]): Whether to prefix tool names with a
                namespace.  ``True`` uses the default ``"langchain tool"``
                namespace; a string is used verbatim.
            include: A name, glob pattern, or list of them to keep.  Matched
                against the raw tool name, the post-namespace name, and the
                snake_case form of each.
            exclude: A name, glob pattern, or list of them to drop.
                Mutually exclusive with *include*.
            allow_replace: Acknowledge replacing an already-registered tool
                under the same name without warning.

        Raises:
            ValueError: If both *include* and *exclude* are given.
            TypeError: If the tool exposes no name or no usable schema.
        """
        self.register_langchain_tools(
            tool,
            namespace,
            include=include,
            exclude=exclude,
            allow_replace=allow_replace,
        )

    def register_langchain_tools(
        self,
        tool: Any,
        namespace: bool | str = False,
        include: str | list[str] | None = None,
        exclude: str | list[str] | None = None,
        allow_replace: bool = False,
    ) -> None:
        """Register a LangChain-style tool (synchronous entry point).

        Args:
            tool: Object exposing ``name``, ``description`` and a schema source.
            namespace (Union[bool, str]): Whether to prefix tool names with a
                namespace.  ``True`` uses the default ``"langchain tool"``
                namespace; a string is used verbatim.
            include: A name, glob pattern, or list of them to keep.
            exclude: A name, glob pattern, or list of them to drop.
            allow_replace: Acknowledge replacing an already-registered tool
                under the same name without warning.

        Raises:
            ValueError: If both *include* and *exclude* are given.
            TypeError: If the tool exposes no name or no usable schema.
        """
        name_filter = ToolNameFilter(include, exclude)

        if isinstance(namespace, str):
            resolved_ns = namespace
        elif namespace:  # namespace is True
            resolved_ns = "langchain tool"
        else:
            resolved_ns = None

        # Filter on the final name before construction: schema extraction
        # can raise, and an explicitly excluded tool must not abort the call.
        sep = self.registry.name_sep
        raw_name = _tool_name(tool)
        candidate_name = qualified_tool_name(raw_name, resolved_ns, sep)
        if not name_filter.accepts(raw_name, candidate_name):
            return

        langchain_tool = LangChainTool.from_langchain_tool(
            tool=tool,
            namespace=resolved_ns,
            sep=sep,
        )
        self.registry.register(
            langchain_tool,
            namespace=resolved_ns,
            allow_replace=allow_replace,
        )
