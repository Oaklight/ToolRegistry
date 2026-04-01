"""Canonical content block types for multimodal tool results.

Defines a lightweight, JSON-compatible representation for multimodal
content using :class:`~typing.TypedDict`.  The ``ImageBlock`` structure
mirrors the Anthropic API format.

All API formats receive text-only tool results.  Multimodal content
is delivered via a subsequent user message produced by
:func:`expand_content_blocks`.  This uniform approach eliminates
per-provider differences in tool result handling.
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


def expand_content_blocks(
    tool_responses: dict[str, str | list],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Separate multimodal content from tool responses for uniform handling.

    For each tool response that contains content blocks (multimodal),
    replaces the value with a placeholder string referencing a
    ``<tool-content>`` tag, and collects the actual content blocks
    into user message content parts that should follow the tool result
    messages.

    This approach is provider-agnostic: all API formats receive
    text-only tool results, and multimodal content is delivered
    via a subsequent user message.

    Args:
        tool_responses: Mapping of tool call IDs to results.
            Values may be ``str`` or ``list[ContentBlock]``.

    Returns:
        A tuple of:

        - **text_only_responses** -- Same mapping but with all content
          block lists replaced by placeholder strings.
        - **extra_user_content** -- List of content parts (dicts) for
          a user message.  Empty if no multimodal content was found.
    """
    text_only: dict[str, str] = {}
    extra_parts: list[dict[str, Any]] = []

    for call_id, result in tool_responses.items():
        if isinstance(result, list) and is_content_block_list(result):
            tag = f'<tool-content call-id="{call_id}">'
            text_only[call_id] = f"See {tag} below."

            # Opening tag
            extra_parts.append({"type": "text", "text": tag})
            # Actual content blocks
            for block in result:
                extra_parts.append(block)
            # Closing tag
            extra_parts.append({"type": "text", "text": "</tool-content>"})
        else:
            text_only[call_id] = result if isinstance(result, str) else str(result)

    return text_only, extra_parts


def build_expanded_user_message(
    content_parts: list[dict[str, Any]],
    api_format: str,
) -> dict[str, Any]:
    """Build a user message from expanded multimodal content parts.

    Converts canonical content blocks (``TextBlock`` / ``ImageBlock``)
    into the user message format required by the target API.

    Args:
        content_parts: List of content block dicts produced by
            :func:`expand_content_blocks`.
        api_format: Target API format (e.g. ``"openai-chat"``,
            ``"anthropic"``, ``"gemini"``).

    Returns:
        A user message dict ready to append to the conversation.
    """
    if api_format in ("openai-chat", "openai-response"):
        parts = []
        for part in content_parts:
            if part.get("type") == "text":
                parts.append({"type": "text", "text": part["text"]})
            elif part.get("type") == "image":
                source = part["source"]
                data_url = f"data:{source['media_type']};base64,{source['data']}"
                parts.append({"type": "image_url", "image_url": {"url": data_url}})
        return {"role": "user", "content": parts}

    elif api_format == "anthropic":
        # Anthropic uses the same format as our canonical content blocks
        return {"role": "user", "content": content_parts}

    elif api_format == "gemini":
        parts = []
        for part in content_parts:
            if part.get("type") == "text":
                parts.append({"text": part["text"]})
            elif part.get("type") == "image":
                source = part["source"]
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": source["media_type"],
                            "data": source["data"],
                        }
                    }
                )
        return {"role": "user", "parts": parts}

    # Fallback: text only
    texts = [p["text"] for p in content_parts if p.get("type") == "text"]
    return {"role": "user", "content": "\n".join(texts)}
