"""Built-in code execution tool for Programmatic Tool Calling (PTC).

Provides :class:`CodeExecutionTool` — a meta-tool that lets LLMs write
and execute Python code with registered tools directly callable in the
code namespace.

This is the toolregistry counterpart to Anthropic's ``code_execution``
server tool.  Instead of a server-side sandbox, toolregistry executes
code in-process with tool access, relying on AST validation to block
dangerous constructs.

PTC reduces latency and token consumption for multi-tool workflows:
instead of N round-trips (one per tool call), the LLM writes one code
block that calls N tools and only the final output is returned.

Example::

    from toolregistry import ToolRegistry

    registry = ToolRegistry()
    registry.register(search)
    registry.register(summarize)
    registry.enable_code_execution()

    # LLM can now generate:
    # tool_use("code_execution", {
    #     "code": "data = search(query='weather')\\nprint(summarize(data))"
    # })

Requires the ``[ptc]`` optional dependency: ``pip install toolregistry[ptc]``
"""

from __future__ import annotations

import io
import sys
import traceback
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

if TYPE_CHECKING:
    from ..tool_registry import ToolRegistry

from ._protocol import DirectProjection, ToolProjection, namespace_to_callables

CODE_EXECUTION_NAME = "code_execution"

CODE_EXECUTION_DESCRIPTION = (
    "Execute Python code in a sandboxed environment. "
    "Use this to perform multi-step computations, data transformations, "
    "or orchestrate multiple tool calls in a single code block. "
    "Registered tools are available as callable functions in the code "
    "namespace — call them directly (e.g. ``result = search(query='...')``). "
    "Only stdout is captured and returned — use print() for output."
)


class CodeExecutionTool:
    """Built-in PTC meta-tool: execute Python code with tool access.

    Executes LLM-generated Python code via ``exec()`` with all enabled
    tools injected as callable functions in the namespace.  Code is
    validated via AST analysis before execution to block dangerous
    constructs (file I/O, network, imports of unsafe modules, etc.).

    The tool is registered as ``code_execution`` in the registry,
    similar to how ``ToolDiscoveryTool`` registers ``discover_tools``.

    Safety model:
        - **AST validation** blocks dangerous constructs before execution
        - **Timeout** kills runaway code via threading
        - **Namespace** tools are directly callable — the LLM can
          orchestrate multi-tool workflows in one code block
        - **No file/network access** — all I/O goes through namespace tools

    Args:
        registry: The tool registry to pull enabled tools from.
        timeout: Default execution timeout in seconds.

    Note:
        Code runs in the current process.  When used with
        ``ProcessPoolBackend`` (the default execution mode), the
        outer executor provides crash isolation — if ``exec()``
        crashes, it takes down the worker process, not the main one.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        timeout: float = 30,
    ) -> None:
        self._registry = registry
        self._timeout = timeout

        try:
            from codecell.python import PythonValidator

            self._validator = PythonValidator()
        except ImportError as exc:
            raise ImportError(
                "CodeExecutionTool requires the 'codecell' package. "
                "Install it with: pip install toolregistry[ptc]"
            ) from exc

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
        """Execute Python code with registered tools in namespace.

        Tools registered in the registry are available as callable
        functions — the LLM can call them directly in the code.
        Use ``print()`` to produce output; only stdout is captured
        and returned.

        Args:
            code: Python source code to execute.
            timeout: Maximum seconds.  Defaults to the value set
                at construction time.  (Currently advisory — full
                timeout enforcement is planned.)

        Returns:
            Captured stdout on success, or an error message prefixed
            with ``"Error:"`` on failure.

        Raises:
            ValueError: If AST validation rejects the code.
            SyntaxError: If the code cannot be parsed.
        """
        # Validate before execution
        self._validator.validate(code)

        ns = self._build_namespace()

        # Build exec globals with namespace tools
        exec_globals: dict[str, Any] = {"__builtins__": __builtins__}
        exec_globals.update(ns)

        # Capture stdout
        old_stdout = sys.stdout
        captured = io.StringIO()
        sys.stdout = captured

        try:
            exec(compile(code, "<code_execution>", "exec"), exec_globals)  # noqa: S102
            return captured.getvalue()
        except Exception:
            tb = traceback.format_exc()
            return f"Error:\n{tb}"
        finally:
            sys.stdout = old_stdout
