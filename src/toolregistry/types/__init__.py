"""Type definitions for toolregistry."""

# Import all types from submodules to maintain backward compatibility
# Type alias for backward compatibility
from typing import Any

from .common import (
    API_FORMATS,
    ToolCall,
    ToolCallResult,
    _normalize_api_format,
    build_assistant_message,
    build_tool_response,
    convert_tool_calls,
    # Deprecated aliases (kept for backward compatibility)
    recover_assistant_message,
    recover_tool_message,
)
from .content_blocks import (
    Base64ImageSource,
    ContentBlock,
    ImageBlock,
    TextBlock,
    content_blocks_to_text,
    is_content_block_list,
)
from .openai import (
    ChatCompetionMessageToolCallResult,
    ChatCompletionMessage,
    ChatCompletionMessageCustomToolCall,
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageToolCall,
    Custom,
    # Chat Completion API
    Function,
    # Response API
    ResponseFunctionToolCall,
    ResponseFunctionToolCallResult,
)

# Type alias for any tool call format - more robust than specific types
AnyToolCall = (
    ChatCompletionMessageFunctionToolCall
    | ChatCompletionMessageCustomToolCall
    | ResponseFunctionToolCall
    | Any
)

__all__ = [
    # Common types and functions
    "ToolCall",
    "ToolCallResult",
    "API_FORMATS",
    "_normalize_api_format",
    "build_assistant_message",
    "build_tool_response",
    "convert_tool_calls",
    # Deprecated aliases
    "recover_assistant_message",
    "recover_tool_message",
    "AnyToolCall",
    # Content block types
    "Base64ImageSource",
    "ContentBlock",
    "ImageBlock",
    "TextBlock",
    "content_blocks_to_text",
    "is_content_block_list",
    # OpenAI Chat Completion API
    "Function",
    "Custom",
    "ChatCompletionMessageFunctionToolCall",
    "ChatCompletionMessageCustomToolCall",
    "ChatCompletionMessageToolCall",
    "ChatCompetionMessageToolCallResult",
    "ChatCompletionMessage",
    # OpenAI Response API
    "ResponseFunctionToolCall",
    "ResponseFunctionToolCallResult",
]
