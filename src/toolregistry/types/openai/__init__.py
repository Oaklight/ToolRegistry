"""OpenAI API types for toolregistry."""

from .chat_completion import (
    ChatCompetionMessageToolCallResult,
    ChatCompletionMessage,
    ChatCompletionMessageCustomToolCall,
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageToolCall,
    Custom,
    Function,
)
from .response import (
    ResponseFunctionToolCall,
    ResponseFunctionToolCallResult,
)

__all__ = [
    # Chat Completion API
    "Function",
    "Custom",
    "ChatCompletionMessageFunctionToolCall",
    "ChatCompletionMessageCustomToolCall",
    "ChatCompletionMessageToolCall",
    "ChatCompetionMessageToolCallResult",
    "ChatCompletionMessage",
    # Response API
    "ResponseFunctionToolCall",
    "ResponseFunctionToolCallResult",
]
