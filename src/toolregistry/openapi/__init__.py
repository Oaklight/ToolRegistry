"""Backward-compatibility shim. Use toolregistry.integrations.openapi instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.openapi' is deprecated. "
    "Use 'toolregistry.integrations.openapi' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.openapi import *  # noqa: E402,F401,F403
from toolregistry.integrations.openapi import __all__  # noqa: E402,F401
