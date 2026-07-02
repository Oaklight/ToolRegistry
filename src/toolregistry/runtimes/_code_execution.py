"""Built-in code execution tool for Programmatic Tool Calling (PTC).

Provides :class:`CodeExecutionTool` — a meta-tool that lets LLMs write
and execute Python code with registered tools directly callable in the
code namespace via subprocess IPC.

Code runs in an isolated subprocess via ``codecell.IpcSubprocessRuntime``.
Tool calls from the code are forwarded back to the main process via
bidirectional JSON-over-pipe IPC — tools retain full access to
connections, env vars, and process-local state.

PTC reduces latency and token consumption for multi-tool workflows:
instead of N round-trips (one per tool call), the LLM writes one code
block that calls N tools and only the final output is returned.

Intermediate tool call results are recorded in a trace log for
debugging and error pinpointing, but are **not** included in the
output returned to the LLM.

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

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..tool_registry import ToolRegistry

from ._protocol import DirectProjection, ToolProjection, validate_namespace

CODE_EXECUTION_NAME = "code_execution"

CODE_EXECUTION_DESCRIPTION = (
    "Execute Python code in a sandboxed subprocess. "
    "Use this to perform multi-step computations, data transformations, "
    "or orchestrate multiple tool calls in a single code block. "
    "Registered tools are available as callable functions in the code "
    "namespace — call them directly (e.g. ``result = search(query='...')``). "
    "Only stdout is captured and returned — use print() for output."
)


# ---------------------------------------------------------------------------
# Tool call trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolCallRecord:
    """Record of a single tool invocation during code execution.

    Attributes:
        tool_name: Name of the tool that was called.
        kwargs: Keyword arguments passed to the tool.
        result: Return value from the tool.
        error: Exception message if the call failed, or ``None``.
        duration_ms: Wall-clock time in milliseconds.
    """

    tool_name: str
    kwargs: dict[str, Any]
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class ExecutionTrace:
    """Trace of all tool calls made during a single code execution.

    Attributes:
        tool_calls: Ordered list of tool call records.
        code: The source code that was executed.
    """

    code: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


def _make_traced_callable(
    proj: ToolProjection,
    trace: ExecutionTrace,
) -> Callable[..., Any]:
    """Wrap a ToolProjection with call tracing.

    The wrapper records every call (args, result, duration, errors)
    into the trace, then returns the result normally.  The LLM code
    sees no difference — it calls tools as usual.
    """

    def wrapper(**kwargs: Any) -> Any:
        t0 = time.perf_counter()
        try:
            result = proj(**kwargs)
            trace.tool_calls.append(
                ToolCallRecord(
                    tool_name=proj.name,
                    kwargs=dict(kwargs),
                    result=result,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
            )
            return result
        except Exception as exc:
            trace.tool_calls.append(
                ToolCallRecord(
                    tool_name=proj.name,
                    kwargs=dict(kwargs),
                    error=str(exc),
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
            )
            raise

    # Preserve name and doc for help() discoverability
    wrapper.__name__ = proj.name
    wrapper.__doc__ = proj.doc
    return wrapper


# ---------------------------------------------------------------------------
# CodeExecutionTool
# ---------------------------------------------------------------------------


class CodeExecutionTool:
    """Built-in PTC meta-tool: execute Python code with tool access.

    Executes LLM-generated Python code in an **isolated subprocess**
    via ``codecell.IpcSubprocessRuntime``.  Registered tools are
    callable from the code via bidirectional IPC — tool execution
    always happens in the main process.

    Intermediate tool call results are recorded in
    :attr:`last_trace` for debugging but are **not** returned to the
    LLM — only ``print()`` output is returned.

    The tool is registered as ``code_execution`` in the registry,
    similar to how ``ToolDiscoveryTool`` registers ``discover_tools``.

    Safety model:
        - **Subprocess isolation** — crashes, OOM, infinite loops
          in code cannot affect the main process
        - **AST validation** blocks dangerous constructs before execution
        - **IPC tool calling** — tools run in main process with full
          access; code runs in subprocess with no direct access
        - **No cloudpickle** — tools never cross the process boundary
        - **Trace logging** records all tool calls for debugging

    Args:
        registry: The tool registry to pull enabled tools from.
        timeout: Default execution timeout in seconds.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        timeout: float = 30,
    ) -> None:
        self._registry = registry
        self._timeout = timeout
        self.last_trace: ExecutionTrace | None = None

        try:
            from codecell import IpcSubprocessRuntime
            from codecell.python import PythonValidator

            self._runtime = IpcSubprocessRuntime(PythonValidator())
        except ImportError as exc:
            raise ImportError(
                "CodeExecutionTool requires the 'codecell' package. "
                "Install it with: pip install toolregistry[ptc]"
            ) from exc

    def _build_namespace(
        self,
        trace: ExecutionTrace,
    ) -> dict[str, Callable[..., Any]]:
        """Build a traced callable namespace from enabled registry tools.

        Each tool is wrapped with :func:`_make_traced_callable` so
        that every invocation is recorded in *trace*.

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

        validate_namespace(projections)

        return {
            name: _make_traced_callable(proj, trace)
            for name, proj in projections.items()
        }

    def execute(self, code: str, timeout: float | None = None) -> str:
        """Execute Python code in a subprocess with tool access via IPC.

        Tools registered in the registry are available as callable
        functions — the LLM can call them directly in the code.
        Tool execution happens in the main process via IPC; only the
        code runs in the subprocess.

        Use ``print()`` to produce output; only stdout is captured
        and returned.

        Intermediate tool call results are recorded in
        :attr:`last_trace` for debugging and error pinpointing.

        Args:
            code: Python source code to execute.
            timeout: Maximum seconds before subprocess is killed.
                Defaults to the value set at construction time.

        Returns:
            Captured stdout on success, or an error message prefixed
            with ``"Error:"`` on failure.

        Raises:
            ValueError: If AST validation rejects the code.
            SyntaxError: If the code cannot be parsed.
        """
        trace = ExecutionTrace(code=code)
        ns = self._build_namespace(trace)

        effective_timeout = timeout if timeout is not None else self._timeout

        try:
            result = self._runtime.execute(
                code,
                namespace=ns,
                timeout=effective_timeout,
            )
        finally:
            self.last_trace = trace

        if result.return_code != 0:
            error = result.stderr.strip()
            return f"Error:\n{error}" if error else "Error: execution failed"

        if result.timed_out:
            return "Error: execution timed out"

        return result.stdout
