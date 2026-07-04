"""Runtime subpackage — PTC (Programmatic Tool Calling) bridge layer.

This subpackage bridges toolregistry's ``Tool`` model into the
``codecell`` code execution engine.

Contents:

- :class:`PtcController` — ``registry.ptc`` controller (enable/disable/track)
- :class:`ToolProjection` — protocol: how a tool appears in code namespace
- :class:`DirectProjection` — in-process ToolProjection (wraps bare callable)
- :func:`validate_namespace` — check key/name consistency
- :func:`namespace_to_callables` — convert ToolProjection dict to
  plain callable dict for codecell

:class:`PtcTool` requires the ``codecell`` package and raises
``ImportError`` on import if it is not installed
(``pip install toolregistry[ptc]``).
"""

from ._protocol import (
    DirectProjection,
    ToolProjection,
    namespace_to_callables,
    validate_namespace,
)
from ._ptc_controller import PTC_TOOL_NAME, PTC_TOOL_DESCRIPTION, PtcController


def __getattr__(name: str):
    """Lazy import for PtcTool — raises ImportError if codecell missing."""
    if name == "PtcTool":
        from ._ptc_tool import PtcTool

        return PtcTool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "PTC_TOOL_DESCRIPTION",
    "PTC_TOOL_NAME",
    "PtcController",
    # PtcTool intentionally excluded — requires codecell [ptc] optional dep.
    # Use: from toolregistry.runtimes import PtcTool (raises ImportError
    # with install instructions if codecell is not installed).
    "DirectProjection",
    "ToolProjection",
    "namespace_to_callables",
    "validate_namespace",
]
