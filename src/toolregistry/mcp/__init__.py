"""Backward-compatibility shim. Use toolregistry.integrations.mcp instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.mcp' is deprecated. "
    "Use 'toolregistry.integrations.mcp' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.mcp import *  # noqa: E402,F401,F403
from toolregistry.integrations.mcp import __all__  # noqa: E402,F401
