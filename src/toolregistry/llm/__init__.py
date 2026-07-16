"""LLM orchestration layer.

This subpackage contains modules that assume the consumer is an LLM:
tool discovery, result truncation, LLM response type conversion,
multimodal content blocks, and the llm-rosetta bridge.

Registry primitives (registration, enable/disable, calling) live in the
parent package and are transport/consumer agnostic.
"""

from .content_blocks import (
    Base64ImageSource,
    ContentBlock,
    ImageBlock,
    TextBlock,
    build_expanded_user_message,
    build_multimodal_user_message,
    content_blocks_to_text,
    expand_content_blocks,
    extract_multimodal_content,
    is_content_block_list,
)
from .tool_calls import (
    API_FORMATS,
    BaseResult,
    ErrorResult,
    ResultList,
    ToolCall,
    ToolCallResult,
    _normalize_api_format,
    build_assistant_message,
    build_assistant_messages,
    build_tool_response,
    build_tool_result_messages,
    convert_tool_calls,
)

__all__ = [
    # Tool call types and functions
    "API_FORMATS",
    "BaseResult",
    "ErrorResult",
    "ResultList",
    "ToolCall",
    "ToolCallResult",
    "_normalize_api_format",
    "build_assistant_message",
    "build_assistant_messages",
    "build_tool_response",
    "build_tool_result_messages",
    "convert_tool_calls",
    # Content block types
    "Base64ImageSource",
    "ContentBlock",
    "ImageBlock",
    "TextBlock",
    "build_expanded_user_message",
    "build_multimodal_user_message",
    "content_blocks_to_text",
    "expand_content_blocks",
    "extract_multimodal_content",
    "is_content_block_list",
]
