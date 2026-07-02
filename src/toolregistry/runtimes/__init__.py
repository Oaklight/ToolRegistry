"""Runtime subpackage — PTC (Programmatic Tool Calling) bridge layer.

This subpackage bridges toolregistry's ``Tool`` model into the
``codecell`` code execution engine.

Contents:

- :class:`ToolProjection` — protocol: how a tool appears in code namespace
- :class:`DirectProjection` — in-process ToolProjection (wraps bare callable)
- :func:`validate_namespace` — check key/name consistency
- :func:`namespace_to_callables` — convert ToolProjection dict to
  plain callable dict for codecell
- :class:`CodeExecutionTool` — built-in PTC meta-tool (requires
  ``codecell``: ``pip install toolregistry[ptc]``)

Code execution types (:class:`~codecell.CodeResult`,
:class:`~codecell.SubprocessRuntime`, etc.) are provided by the
``codecell`` package.
"""

from ._code_execution import CODE_EXECUTION_NAME, CodeExecutionTool
from ._protocol import (
    DirectProjection,
    ToolProjection,
    namespace_to_callables,
    validate_namespace,
)

__all__ = [
    "CODE_EXECUTION_NAME",
    "CodeExecutionTool",
    "DirectProjection",
    "ToolProjection",
    "namespace_to_callables",
    "validate_namespace",
]
