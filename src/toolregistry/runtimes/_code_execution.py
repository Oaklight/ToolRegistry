"""Built-in code execution tool for Programmatic Tool Calling (PTC).

Provides :class:`CodeExecutionTool` — a meta-tool that lets LLMs write
and execute Python code in a sandboxed subprocess.  Registered tools
are injected into the code's namespace so the LLM can orchestrate
multi-tool workflows in a single code block.

This is the toolregistry counterpart to Anthropic's ``code_execution``
server tool.  Instead of a server-side sandbox, toolregistry hosts the
runtime locally via the ``codecell`` package.

PTC reduces latency and token consumption for multi-tool workflows:
instead of N round-trips (one per tool call), the LLM writes one code
block that calls N tools and only the final output is returned.

Example::

    from toolregistry import ToolRegistry

    registry = ToolRegistry()
    registry.register(search)
    registry.register(summarize)
    registry.enable_code_execution()  # registers "code_execution" tool

    # LLM can now generate:
    # tool_use("code_execution", {
    #     "code": "data = search(query='weather')\\nprint(summarize(data))"
    # })

Requires the ``[ptc]`` optional dependency: ``pip install toolregistry[ptc]``
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from collections.abc import Callable

if TYPE_CHECKING:
    from ..tool_registry import ToolRegistry

from ._protocol import DirectProjection, ToolProjection, namespace_to_callables

CODE_EXECUTION_NAME = "code_execution"

_CODE_EXECUTION_DESCRIPTION = (
    "Execute Python code in a sandboxed subprocess. "
    "Use this to perform multi-step computations, data transformations, "
    "or orchestrate multiple tool calls in a single code block. "
    "Registered tools are available as callable functions in the code namespace. "
    "Only stdout is captured and returned — use print() for output."
)


class CodeExecutionTool:
    """Built-in PTC meta-tool: execute Python code with tool access.

    Creates a sandboxed Python subprocess via ``codecell``, injects
    all enabled tools as callable functions into the namespace, and
    returns the captured stdout.

    The tool is registered as ``code_execution`` in the registry,
    similar to how ``ToolDiscoveryTool`` registers ``discover_tools``.

    Args:
        registry: The tool registry to pull enabled tools from.
        timeout: Default execution timeout in seconds.

    Note:
        In the current subprocess mode, namespace functions are
        injected as **stubs** that raise ``NotImplementedError``
        when called.  This allows LLMs to discover available tools
        via ``help()`` but not actually invoke them across the
        process boundary.  Full IPC-based calling is planned for
        a future release (see issue #177).
    """

    def __init__(
        self,
        registry: ToolRegistry,
        timeout: float = 30,
    ) -> None:
        self._registry = registry
        self._timeout = timeout

        try:
            from codecell import SubprocessRuntime
            from codecell.python import PythonValidator
        except ImportError as exc:
            raise ImportError(
                "CodeExecutionTool requires the 'codecell' package. "
                "Install it with: pip install toolregistry[ptc]"
            ) from exc

        self._runtime = SubprocessRuntime(PythonValidator())

    def _build_namespace(self) -> dict[str, Callable[..., Any]]:
        """Build a callable namespace from enabled registry tools.

        Converts each enabled tool into a :class:`DirectProjection`
        and then into a plain callable dict via
        :func:`namespace_to_callables`.

        The ``code_execution`` tool itself is excluded to prevent
        recursive invocation.
        """
        projections: dict[str, ToolProjection] = {}
        for name in self._registry.list_tools():
            if name == CODE_EXECUTION_NAME:
                continue
            tool = self._registry.get_tool(name)
            if tool is None:
                continue
            projections[tool.name] = DirectProjection(
                name=tool.name,
                fn=tool.fn,
                doc=tool.description,
            )
        return namespace_to_callables(projections)

    def execute(self, code: str, timeout: float | None = None) -> str:
        """Execute Python code in a sandboxed subprocess.

        Registered tools are available as functions in the code
        namespace.  Use ``print()`` to produce output — only stdout
        is captured and returned to the LLM.

        Args:
            code: Python source code to execute.
            timeout: Maximum seconds before kill.  Defaults to the
                value set at construction time.

        Returns:
            Captured stdout on success, or an error message prefixed
            with ``"Error:"`` on failure.
        """
        ns = self._build_namespace()
        effective_timeout = timeout if timeout is not None else self._timeout

        result = self._runtime.execute(
            code,
            namespace=ns,
            timeout=effective_timeout,
        )

        if result.return_code != 0:
            error = result.stderr.strip()
            return f"Error:\n{error}" if error else "Error: execution failed"

        return result.stdout
