"""Lazy-import helpers for llm-rosetta integration.

Provides a thin wrapper around :mod:`llm_rosetta.tool_ops` for
provider-specific ToolOps dispatch, and a helper to build IR
tool definition dicts.
"""

from __future__ import annotations

from typing import Any


def _get_tool_ops(provider: str) -> Any:
    """Return the ToolOps class for *provider* via llm-rosetta dispatch.

    Args:
        provider: Canonical provider name (e.g. ``"openai_chat"``,
            ``"google"``, ``"google_interactions"``).

    Returns:
        The corresponding ToolOps class.
    """
    from llm_rosetta.tool_ops import _get_tool_ops as _rosetta_get_tool_ops

    return _rosetta_get_tool_ops(provider)


def _make_ir_tool_definition(
    name: str, description: str, parameters: dict[str, Any]
) -> dict[str, Any]:
    """Build an IR ToolDefinition dict from Tool attributes.

    Args:
        name: Tool name.
        description: Tool description.
        parameters: JSON Schema dict for parameters.

    Returns:
        IR ToolDefinition dict compatible with llm-rosetta converters.
    """
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": parameters,
    }
