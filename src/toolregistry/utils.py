"""Shared helpers kept as the compatibility surface.

The implementations live next to their concern: tool-name rules in
:mod:`toolregistry._names`, HTTP client glue in :mod:`toolregistry._http`, and
result encoding in :mod:`toolregistry._serialisation`.  Every name this
module exported before the split is still importable here, so downstream
packages and existing documentation keep working.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from ._http import (
    DEFAULT_MAX_TOOL_RESPONSE_BYTES,
    HttpClientConfig,
    HttpxClientConfig,
    OpenAPIPathError,
    _BaseUrlAsyncClient,
    _BaseUrlClient,
    _URL_USERINFO_BARE,
    _URL_USERINFO_NETLOC,
    _URL_USERINFO_SCHEME,
    _join_base_url,
    _join_base_url_path,
    redact_url_userinfo,
)
from ._names import (
    ToolNameFilter,
    _as_pattern_list,
    _name_spellings,
    normalize_tool_name,
)
from ._serialisation import (
    ToolResultJSONEncoder,
    _STR_LIKE_SCALARS,
    _copy_into,
    _replace_non_finite,
    _sanitise_float,
    encode_tool_result,
)

__all__ = [
    "DEFAULT_MAX_TOOL_RESPONSE_BYTES",
    "HttpClientConfig",
    "HttpxClientConfig",
    "OpenAPIPathError",
    "ToolNameFilter",
    "ToolResultJSONEncoder",
    "_BaseUrlAsyncClient",
    "_BaseUrlClient",
    "_STR_LIKE_SCALARS",
    "_URL_USERINFO_BARE",
    "_URL_USERINFO_NETLOC",
    "_URL_USERINFO_SCHEME",
    "_as_pattern_list",
    "_copy_into",
    "_join_base_url",
    "_join_base_url_path",
    "_name_spellings",
    "_replace_non_finite",
    "_sanitise_float",
    "compute_schema_hash",
    "encode_tool_result",
    "generate_invocation_id",
    "normalize_tool_name",
    "redact_url_userinfo",
    "utc_iso_now",
]


def generate_invocation_id(prefix: Literal["bat", "ptc", "sig"] = "sig") -> str:
    """Generate a unique invocation ID for grouping related tool calls.

    Prefixes:
        - ``tr_bat_`` — batch execution via ``execute_tool_calls()``
        - ``tr_ptc_`` — PTC code execution via ``PtcTool``
        - ``tr_sig_`` — single invocation via ``registry.invoke()``

    Args:
        prefix: One of ``"bat"``, ``"ptc"``, ``"sig"``.

    Returns:
        A unique ID like ``"tr_bat_a1b2c3d4"``.
    """
    return f"tr_{prefix}_{uuid.uuid4().hex[:8]}"


def compute_schema_hash(parameters: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hex digest of a JSON Schema dict.

    Args:
        parameters: The JSON Schema dict (typically ``Tool.parameters``).

    Returns:
        A 64-character lowercase hex string.
    """
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def utc_iso_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()
