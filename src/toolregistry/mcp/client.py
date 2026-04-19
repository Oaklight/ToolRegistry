"""Backward-compatibility shim. Use toolregistry.integrations.mcp.client instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.mcp.client' is deprecated. "
    "Use 'toolregistry.integrations.mcp.client' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.mcp.client import MCPClient, _to_stdio_params  # noqa: E402,F401
