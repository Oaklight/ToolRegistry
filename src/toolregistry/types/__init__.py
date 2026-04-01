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
