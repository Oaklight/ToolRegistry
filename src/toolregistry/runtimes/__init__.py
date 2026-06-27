"""Runtime subpackage — PTC (Programmatic Tool Calling) protocols and runtimes.

This subpackage has **zero imports from toolregistry internals**.
It operates exclusively on callables, dicts, and its own protocol types.

Current contents:

- :class:`CodeResult` — structured output from code execution
- :class:`ToolProjection` — protocol: how a tool appears in code namespace
- :class:`DirectProjection` — in-process ToolProjection (wraps bare callable)
- :class:`CodeRuntime` — protocol: executes code with tool access

Future contents (see issues #176, #177):

- ``InProcessRuntime`` — ``exec()``-based CodeRuntime
- ``SubprocessRuntime`` — isolated CodeRuntime with bidirectional IPC
- ``PythonExecutionTool`` — meta-tool exposing CodeRuntime to LLMs
"""

from ._protocol import (
    CodeResult,
    CodeRuntime,
    DirectProjection,
    ToolProjection,
    validate_namespace,
)

__all__ = [
    "CodeResult",
    "CodeRuntime",
    "DirectProjection",
    "ToolProjection",
    "validate_namespace",
]
