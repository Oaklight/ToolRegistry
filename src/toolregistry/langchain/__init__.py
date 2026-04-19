"""Backward-compatibility shim. Use toolregistry.integrations.langchain instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.langchain' is deprecated. "
    "Use 'toolregistry.integrations.langchain' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.langchain import *  # noqa: E402,F401,F403
from toolregistry.integrations.langchain import __all__  # noqa: E402,F401
