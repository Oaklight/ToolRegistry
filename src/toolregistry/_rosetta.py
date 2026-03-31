"""Lazy-import helpers for llm-rosetta integration.

Provides accessor functions that import llm-rosetta converter components
on demand to avoid circular imports and reduce startup cost.
"""

from __future__ import annotations

from typing import Any


def _get_openai_chat_tool_ops() -> Any:
    """Lazily import OpenAIChatToolOps from llm-rosetta."""
    from llm_rosetta.converters.openai_chat.tool_ops import OpenAIChatToolOps

    return OpenAIChatToolOps


def _get_openai_responses_tool_ops() -> Any:
    """Lazily import OpenAIResponsesToolOps from llm-rosetta."""
    from llm_rosetta.converters.openai_responses.tool_ops import (
        OpenAIResponsesToolOps,
    )

    return OpenAIResponsesToolOps


def _get_anthropic_tool_ops() -> Any:
    """Lazily import AnthropicToolOps from llm-rosetta."""
    from llm_rosetta.converters.anthropic.tool_ops import AnthropicToolOps

    return AnthropicToolOps


def _get_google_tool_ops() -> Any:
    """Lazily import GoogleGenAIToolOps from llm-rosetta."""
    from llm_rosetta.converters.google_genai.tool_ops import GoogleGenAIToolOps

    return GoogleGenAIToolOps


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
