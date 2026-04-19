"""Backward-compatibility shim. Use toolregistry.integrations.native instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.native' is deprecated. "
    "Use 'toolregistry.integrations.native' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.native import *  # noqa: E402,F401,F403
from toolregistry.integrations.native import __all__  # noqa: E402,F401
