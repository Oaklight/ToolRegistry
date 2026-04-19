"""Backward-compatibility shim. Use toolregistry.integrations.mcp.connection instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.mcp.connection' is deprecated. "
    "Use 'toolregistry.integrations.mcp.connection' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.mcp.connection import MCPConnectionManager  # noqa: E402,F401
