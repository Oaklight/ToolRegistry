"""Backward-compatibility shim. Use toolregistry.integrations.native.utils instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.native.utils' is deprecated. "
    "Use 'toolregistry.integrations.native.utils' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.native.utils import (  # noqa: E402,F401
    _determine_namespace,
    _is_all_static_methods,
    get_all_static_methods,
)
