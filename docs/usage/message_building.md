---
title: Message Building
summary: Build conversation messages for tool-calling round-trips
description: How to use build_assistant_message, build_tool_response, and build_tool_call_messages to construct LLM conversation history
keywords: message building, tool calls, assistant message, tool response, conversation history
author: Oaklight
---

# Message Building

After executing tool calls, you need to construct conversation messages so the LLM can process the results and continue the dialogue. ToolRegistry provides three functions for this purpose.

## Overview

| Function | Level | Input | Output |
|----------|-------|-------|--------|
| `build_assistant_message()` | Module | `list[ToolCall]` | Assistant message with tool call requests |
| `build_tool_response()` | Module | `dict[str, str]` | Tool result messages |
| `build_tool_call_messages()` | `ToolRegistry` method | Raw tool calls + responses | Combined assistant + tool messages |

In most cases, you only need `build_tool_call_messages()` — the high-level convenience method that handles everything.

## `build_tool_call_messages()`

Combines the assistant message (what the LLM decided to call) and the tool results into the messages required for the next LLM turn.

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

# After LLM returns tool_calls and you execute them:
tool_responses = registry.execute_tool_calls(tool_calls)

# Build conversation messages for the next turn
messages = registry.build_tool_call_messages(
    tool_calls, tool_responses, api_format="openai-chat"
)

# Extend your conversation history
conversation.extend(messages)
```

### Gemini ID Alignment

Gemini does not provide tool call IDs upstream — ToolRegistry generates them internally. `build_tool_call_messages()` handles this transparently via position-based ID remapping: it aligns the generated IDs in `tool_calls` with the IDs in `tool_responses` by position.

!!! warning "Do not reorder tool_calls"
    You **must not** reorder the `tool_calls` list between calling `execute_tool_calls()` and `build_tool_call_messages()`. Both methods process tool calls in the same order, and Gemini format relies on this positional alignment. Reordering would cause mismatched function names in the output.

## `build_assistant_message()`

Low-level function that reconstructs just the assistant-side message containing tool call requests.

```python
from toolregistry.types.common import build_assistant_message, ToolCall

tool_calls = [
    ToolCall(id="call_1", name="add", arguments='{"a": 1, "b": 2}')
]

# Returns the assistant message in the target format
assistant_msg = build_assistant_message(tool_calls, api_format="openai-chat")
```

### Scope and Boundaries

This function **only handles tool calls**. It does not handle:

- **`content`** — text content returned alongside tool calls
- **`thinking` / `reasoning_content`** — chain-of-thought from third-party OpenAI-compatible APIs
- **`thought_signature`** — Google's thinking metadata
- **Any other vendor-specific fields**

If the LLM returns mixed content (text + tool calls), you must preserve non-tool-call fields yourself from the original response.

## `build_tool_response()`

Low-level function that reconstructs tool result messages from execution responses.

```python
from toolregistry.types.common import build_tool_response

tool_responses = {"call_1": "3.0", "call_2": "7.0"}

# Returns tool result messages in the target format
tool_msgs = build_tool_response(tool_responses, api_format="openai-chat")
```

### Gemini Name Resolution

For Gemini format, `functionResponse` requires the function **name** (not the call ID). Pass `tool_calls` to enable name resolution:

```python
tool_msgs = build_tool_response(
    tool_responses,
    api_format="gemini",
    tool_calls=generic_tool_calls,  # Required for Gemini
)
```

Without `tool_calls`, the function falls back to using the call ID as the name, which produces incorrect Gemini messages.

## API Format Values

The `api_format` parameter accepts these values:

| Value | Description |
|-------|-------------|
| `"openai-chat"` | OpenAI Chat Completion format (default, canonical) |
| `"openai-response"` | OpenAI Response API format |
| `"anthropic"` | Anthropic Messages API format |
| `"gemini"` | Google Gemini API format |
| `"openai"` | **Deprecated** — alias for `"openai-chat"` |
| `"openai-chatcompletion"` | **Deprecated** — alias for `"openai-chat"` |

Using deprecated format names emits a `DeprecationWarning`.

## Risk Summary

| Risk | Affected Function | Mitigation |
|------|-------------------|------------|
| Reordering `tool_calls` breaks Gemini ID alignment | `build_tool_call_messages()` | Never reorder between `execute_tool_calls()` and `build_tool_call_messages()` |
| Missing `tool_calls` param produces wrong Gemini names | `build_tool_response()` | Always pass `tool_calls` for Gemini format |
| Mixed content (text + tool calls) silently dropped | `build_assistant_message()` | Preserve non-tool-call content from original response yourself |
| `tool_responses` dict order matters for Gemini | `build_tool_call_messages()` | Python 3.7+ dicts preserve insertion order; do not reconstruct the dict |

## Deprecated Names

The following old names still work but emit `DeprecationWarning`:

| Old Name | New Name |
|----------|----------|
| `recover_assistant_message()` | `build_assistant_message()` |
| `recover_tool_message()` | `build_tool_response()` |
| `registry.recover_tool_call_assistant_message()` | `registry.build_tool_call_messages()` |
| `registry.get_tools_json()` | `registry.get_schemas()` |
