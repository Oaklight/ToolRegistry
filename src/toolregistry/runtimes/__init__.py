"""Runtime subpackage -- agent infrastructure tools and code execution runtimes.

This subpackage hosts tools that are part of the agent infrastructure layer
(not domain-specific), and will eventually contain the PTC (Programmatic
Tool Calling) code execution runtimes.

Current contents:

- :class:`BashTool` -- shell command execution with safety validation
  (via the ``bashtool`` submodule)

Future contents (see issue #175+):

- ``CodeRuntime`` / ``ToolProjection`` protocols
- ``InProcessRuntime``, ``SubprocessRuntime``
- ``PythonExecutionTool``
"""

from ._bashtool import BashTool, truncate, validate_command

__all__ = ["BashTool", "truncate", "validate_command"]
