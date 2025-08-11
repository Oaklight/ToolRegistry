"""Type definitions for toolregistry."""

# Import all types from submodules to maintain backward compatibility
# Type alias for backward compatibility
from typing import Any, Union

from .common import (
    API_FORMATS,
    ToolCall,
    ToolCallResult,
    convert_tool_calls,
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
AnyToolCall = Union[
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageCustomToolCall,
    ResponseFunctionToolCall,
    Any,
]

__all__ = [
    # Common types and functions
    "ToolCall",
    "ToolCallResult",
    "API_FORMATS",
    "convert_tool_calls",
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
