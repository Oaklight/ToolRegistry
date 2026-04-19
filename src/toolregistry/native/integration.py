"""Backward-compatibility shim. Use toolregistry.integrations.native.integration instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.native.integration' is deprecated. "
    "Use 'toolregistry.integrations.native.integration' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.native.integration import ClassToolIntegration  # noqa: E402,F401
