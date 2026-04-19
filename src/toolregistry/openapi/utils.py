"""Backward-compatibility shim. Use toolregistry.integrations.openapi.utils instead."""

import warnings

warnings.warn(
    "Importing from 'toolregistry.openapi.utils' is deprecated. "
    "Use 'toolregistry.integrations.openapi.utils' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from toolregistry.integrations.openapi.utils import (  # noqa: E402,F401
    determine_urls,
    extract_base_url_from_specs,
    load_openapi_spec,
    load_openapi_spec_async,
)
