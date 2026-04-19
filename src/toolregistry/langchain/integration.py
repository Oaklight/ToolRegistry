"""Backward-compatibility shim. Use toolregistry.integrations.langchain.integration instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.langchain.integration' is deprecated. "
    "Use 'toolregistry.integrations.langchain.integration' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.langchain.integration import (  # noqa: E402,F401
    LangChainIntegration,
    LangChainTool,
    LangChainToolWrapper,
)
