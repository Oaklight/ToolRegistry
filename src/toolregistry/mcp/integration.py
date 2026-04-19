"""Backward-compatibility shim. Use toolregistry.integrations.mcp.integration instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.mcp.integration' is deprecated. "
    "Use 'toolregistry.integrations.mcp.integration' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.mcp.integration import (  # noqa: E402,F401
    MCPIntegration,
    MCPTool,
    MCPToolWrapper,
)
