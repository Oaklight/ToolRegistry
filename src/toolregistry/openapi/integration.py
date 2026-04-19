"""Backward-compatibility shim. Use toolregistry.integrations.openapi.integration instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.openapi.integration' is deprecated. "
    "Use 'toolregistry.integrations.openapi.integration' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.openapi.integration import (  # noqa: E402,F401
    OpenAPIIntegration,
    OpenAPITool,
    OpenAPIToolWrapper,
)
