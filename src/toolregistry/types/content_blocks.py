"""Canonical content block types for multimodal tool results.

Defines a lightweight, JSON-compatible representation for multimodal
content using :class:`~typing.TypedDict`.  The ``ImageBlock`` structure
mirrors the Anthropic API format so that the Anthropic path in
:func:`build_tool_response` can pass it through without transformation.

Only Anthropic natively supports multimodal content in tool results.
For other providers (OpenAI, Gemini), :func:`content_blocks_to_text`
provides a text-only fallback.
"""

from __future__ import annotations

import base64
from typing import Any, Literal, TypedDict, Union


class TextBlock(TypedDict):
    """A plain text content block."""

    type: Literal["text"]
    text: str


class Base64ImageSource(TypedDict):
    """Base64-encoded image data with media type."""

    type: Literal["base64"]
    media_type: str  # e.g. "image/png"
    data: str  # base64-encoded string


class ImageBlock(TypedDict):
    """An image content block with base64-encoded source."""

    type: Literal["image"]
    source: Base64ImageSource


ContentBlock = Union[TextBlock, ImageBlock]
"""Union type for all supported content block kinds."""

_CONTENT_BLOCK_TYPES = {"text", "image"}


def is_content_block_list(value: Any) -> bool:
    """Check whether *value* is a list of content blocks.

    A valid content block list is a non-empty ``list`` where every
    element is a ``dict`` with a ``"type"`` key whose value is one of
    the recognized content block types (``"text"`` or ``"image"``).

    Args:
        value: The value to check.

    Returns:
        ``True`` if *value* conforms to the content block list shape.
    """
    if not isinstance(value, list) or len(value) == 0:
        return False
    return all(
        isinstance(item, dict) and item.get("type") in _CONTENT_BLOCK_TYPES
        for item in value
    )


def content_blocks_to_text(blocks: list[ContentBlock]) -> str:
    """Render content blocks as a plain-text string.

    Text blocks are concatenated directly.  Image blocks are replaced
    with a human-readable placeholder indicating the media type and
    approximate data size.

    Args:
        blocks: List of content blocks to render.

    Returns:
        A plain-text representation of the content.
    """
    parts: list[str] = []
    for block in blocks:
        if block["type"] == "text":
            parts.append(block["text"])
        elif block["type"] == "image":
            source = block["source"]
            media_type = source.get("media_type", "unknown")
            data = source.get("data", "")
            try:
                byte_size = len(base64.b64decode(data))
            except Exception:
                byte_size = len(data)
            parts.append(f"[Image: {media_type}, {byte_size} bytes]")
    return "\n".join(parts)
