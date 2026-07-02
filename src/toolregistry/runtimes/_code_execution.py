"""Built-in code execution tool for Programmatic Tool Calling (PTC).

Provides :class:`CodeExecutionTool` — a meta-tool that lets LLMs write
and execute Python code with registered tools directly callable in the
code namespace via subprocess IPC.

Code runs in an isolated subprocess via ``codecell.IpcSubprocessRuntime``.
Tool calls from the code are forwarded back to the main process via
bidirectional JSON-over-pipe IPC — tools retain full access to
connections, env vars, and process-local state.

All tool calls are logged in the registry's execution log with a
shared ``invocation_id`` (prefix ``tr_ptc_``) so the complete call
chain for a single PTC execution can be queried.

Example::

    from toolregistry import ToolRegistry

    registry = ToolRegistry()
    registry.register(search)
    registry.register(summarize)
    registry.enable_code_execution()
    registry.enable_logging()

    # LLM generates:
    # tool_use("code_execution", {
    #     "code": "data = search(query='weather')\\nprint(summarize(data))"
    # })

    # Query all tool calls from the last PTC execution:
    # log.get_entries(invocation_id=executor.last_invocation_id)

Requires the ``[ptc]`` optional dependency: ``pip install toolregistry[ptc]``
"""

from __future__ import annotations

from collections.abc import Callable
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


class CodeExecutionTool:
    """Built-in PTC meta-tool: execute Python code with tool access.

    Executes LLM-generated Python code in an **isolated subprocess**
    via ``codecell.IpcSubprocessRuntime``.  Registered tools are
    callable from the code via bidirectional IPC — tool execution
    always happens in the main process via ``registry.invoke()``.

    Tool calls are logged in the registry's execution log with a
    shared ``invocation_id`` (prefix ``tr_ptc_``).  Use
    :attr:`last_invocation_id` to query all calls from the last
    execution.

    Safety model:
        - **Subprocess isolation** — crashes, OOM, infinite loops
          in code cannot affect the main process
        - **AST validation** blocks dangerous constructs before execution
        - **IPC tool calling** — tools run in main process via
          ``registry.invoke()`` with full permissions and logging
        - **No cloudpickle** — tools never cross the process boundary

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
        self.last_invocation_id: str | None = None

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
        invocation_id: str,
    ) -> dict[str, Callable[..., Any]]:
        """Build a callable namespace from enabled registry tools.

        Each tool call goes through ``registry.invoke()`` with the
        shared *invocation_id*, ensuring permissions are checked and
        the call is logged.

        The ``code_execution`` tool itself is excluded to prevent
        recursive invocation.
        """
        projections: dict[str, ToolProjection] = {}
        registry = self._registry
        for name in registry.list_tools():
            if name == CODE_EXECUTION_NAME:
                continue
            tool = registry.get_tool(name)
            if tool is None:
                continue

            tool_name = tool.name

            def _make_invoke_fn(tn: str) -> Callable[..., Any]:
                def fn(**kwargs: Any) -> Any:
                    return registry.invoke(tn, kwargs, invocation_id=invocation_id)

                return fn

            projections[tool_name] = DirectProjection(
                name=tool_name,
                fn=_make_invoke_fn(tool_name),
                doc=tool.description,
            )

        validate_namespace(projections)
        return {name: proj for name, proj in projections.items()}

    def execute(self, code: str, timeout: float | None = None) -> str:
        """Execute Python code in a subprocess with tool access via IPC.

        Tools registered in the registry are available as callable
        functions — the LLM can call them directly in the code.
        Tool execution happens in the main process via
        ``registry.invoke()`` with permissions and logging.

        Use ``print()`` to produce output; only stdout is captured
        and returned.

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
        from ..utils import generate_invocation_id

        inv_id = generate_invocation_id("ptc")
        self.last_invocation_id = inv_id

        ns = self._build_namespace(inv_id)
        effective_timeout = timeout if timeout is not None else self._timeout

        result = self._runtime.execute(
            code,
            namespace=ns,
            timeout=effective_timeout,
        )

        if result.timed_out:
            return "Error: execution timed out"

        if result.return_code != 0:
            error = result.stderr.strip()
            return f"Error:\n{error}" if error else "Error: execution failed"

        return result.stdout
