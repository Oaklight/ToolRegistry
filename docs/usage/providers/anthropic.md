# Anthropic Integration

???+ note "Changelog"
    New in version: 0.7.0

This guide shows how to use ToolRegistry with the [Anthropic API](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) (Claude). ToolRegistry generates Anthropic-native tool schemas and reconstructs `tool_use` / `tool_result` messages for multi-turn conversations.

## Setup ToolRegistry

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

@registry.register
def subtract(a: float, b: float) -> float:
    """Subtract the second number from the first."""
    return a - b
```

## Exposing Tool Schemas

```python
schemas = registry.get_tools_json(api_format="anthropic")
```

This returns tools in Anthropic's format:

```json
[
  {
    "name": "add",
    "description": "Add two numbers together.",
    "input_schema": {
      "properties": {
        "a": { "title": "A", "type": "number" },
        "b": { "title": "B", "type": "number" }
      },
      "required": ["a", "b"],
      "title": "addParameters",
      "type": "object"
    }
  },
  {
    "name": "subtract",
    "description": "Subtract the second number from the first.",
    "input_schema": {
      "properties": {
        "a": { "title": "A", "type": "number" },
        "b": { "title": "B", "type": "number" }
      },
      "required": ["a", "b"],
      "title": "subtractParameters",
      "type": "object"
    }
  }
]
```

## Supply Query with Tool Schema

```python
import os
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

messages = [
    {"role": "user", "content": "I have 15 chestnuts. Joe ate 3. How many do I have left?"}
]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=schemas,
    messages=messages,
)
```

## Extract Tool Calls

Anthropic returns tool use as `tool_use` content blocks:

```python
tool_calls = [block for block in response.content if block.type == "tool_use"]
```

Example `tool_use` block:

```json
{
  "type": "tool_use",
  "id": "toolu_01A09q90qw90lq917835lq9",
  "name": "subtract",
  "input": {"a": 15, "b": 3}
}
```

## Execute Tool Calls

ToolRegistry handles Anthropic `tool_use` blocks natively:

```python
tool_responses = registry.execute_tool_calls(tool_calls)
```

Returns a dict mapping tool call IDs to results:

```json
{"toolu_01A09q90qw90lq917835lq9": "12"}
```

## Feed Results Back to LLM

Reconstruct the conversation messages in Anthropic format:

```python
assistant_tool_messages = registry.recover_tool_call_assistant_message(
    tool_calls, tool_responses, api_format="anthropic"
)
```

This produces Anthropic-native message structure:

```json
[
  {
    "role": "assistant",
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_01A09q90qw90lq917835lq9",
        "name": "subtract",
        "input": {"a": 15, "b": 3}
      }
    ]
  },
  {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu_01A09q90qw90lq917835lq9",
        "content": "12"
      }
    ]
  }
]
```

Extend the conversation and get the final answer:

```python
messages.extend(assistant_tool_messages)

second_response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=messages,
)

print(second_response.content[0].text)
```

## Complete Python Script

```python
import json
import os

import anthropic
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

@registry.register
def subtract(a: float, b: float) -> float:
    """Subtract the second number from the first."""
    return a - b

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

messages = [
    {"role": "user", "content": "I have 15 chestnuts. Joe ate 3. How many do I have left?"}
]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=registry.get_tools_json(api_format="anthropic"),
    messages=messages,
)

tool_calls = [block for block in response.content if block.type == "tool_use"]

if tool_calls:
    tool_responses = registry.execute_tool_calls(tool_calls)
    print(tool_responses)

    assistant_tool_messages = registry.recover_tool_call_assistant_message(
        tool_calls, tool_responses, api_format="anthropic"
    )
    print(json.dumps(assistant_tool_messages, indent=2))

    messages.extend(assistant_tool_messages)
    second_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=messages,
    )

    print(second_response.content[0].text)
```

## See Also

- [Anthropic Tool Use Documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Architecture Overview](../../architecture/overview.md) — how ToolRegistry generates multi-format schemas via llm-rosetta
