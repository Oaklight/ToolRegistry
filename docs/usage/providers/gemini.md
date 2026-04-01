# Google Gemini Integration

???+ note "Changelog"
    New in version: 0.7.0

This guide shows how to use ToolRegistry with the [Google Gemini API](https://ai.google.dev/gemini-api/docs/function-calling). ToolRegistry generates Gemini-native function declarations and reconstructs `functionCall` / `functionResponse` messages for multi-turn conversations.

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
schemas = registry.get_tools_json(api_format="gemini")
```

This returns tools in Gemini's function declaration format:

```json
[
  {
    "name": "add",
    "description": "Add two numbers together.",
    "parameters": {
      "type": "object",
      "properties": {
        "a": { "type": "number" },
        "b": { "type": "number" }
      },
      "required": ["a", "b"]
    }
  }
]
```

## Supply Query with Tool Schema

```python
import os
from google import genai

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# Wrap schemas in the tools structure Gemini expects
tools = [{"function_declarations": schemas}]

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="I have 15 chestnuts. Joe ate 3. How many do I have left?",
    config={"tools": tools},
)
```

## Extract Tool Calls

Gemini returns function calls as `functionCall` parts within the response:

```python
tool_calls = [
    part for part in response.candidates[0].content.parts
    if hasattr(part, "function_call") and part.function_call
]
```

Example `functionCall` part (as dict):

```json
{
  "functionCall": {
    "name": "subtract",
    "args": {"a": 15, "b": 3}
  }
}
```

## Execute Tool Calls

ToolRegistry handles Gemini `functionCall` parts natively:

```python
tool_responses = registry.execute_tool_calls(tool_calls)
```

## Feed Results Back to LLM

Reconstruct the conversation messages in Gemini format:

```python
assistant_tool_messages = registry.recover_tool_call_assistant_message(
    tool_calls, tool_responses, api_format="gemini"
)
```

This produces Gemini-native message structure:

```json
[
  {
    "role": "model",
    "parts": [
      {
        "functionCall": {
          "name": "subtract",
          "args": {"a": 15, "b": 3}
        }
      }
    ]
  },
  {
    "role": "user",
    "parts": [
      {
        "functionResponse": {
          "name": "subtract",
          "response": {"output": "12.0"}
        }
      }
    ]
  }
]
```

Continue the conversation:

```python
from google.genai.types import Content, Part

# Build conversation history for the next turn
history = [
    Content(role="user", parts=[Part(text="I have 15 chestnuts. Joe ate 3. How many do I have left?")]),
]

# Add the tool call and result messages
for msg in assistant_tool_messages:
    role = msg["role"]
    parts = []
    for p in msg["parts"]:
        if "functionCall" in p:
            parts.append(Part(function_call=p["functionCall"]))
        elif "functionResponse" in p:
            parts.append(Part(function_response=p["functionResponse"]))
    history.append(Content(role=role, parts=parts))

second_response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=history,
)

print(second_response.text)
```

## Complete Python Script

```python
import json
import os

from google import genai
from google.genai.types import Content, Part
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

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

schemas = registry.get_tools_json(api_format="gemini")
tools = [{"function_declarations": schemas}]

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="I have 15 chestnuts. Joe ate 3. How many do I have left?",
    config={"tools": tools},
)

tool_calls = [
    part for part in response.candidates[0].content.parts
    if hasattr(part, "function_call") and part.function_call
]

if tool_calls:
    tool_responses = registry.execute_tool_calls(tool_calls)
    print(tool_responses)

    assistant_tool_messages = registry.recover_tool_call_assistant_message(
        tool_calls, tool_responses, api_format="gemini"
    )
    print(json.dumps(assistant_tool_messages, indent=2))

    # Build history for continuation
    history = [
        Content(role="user", parts=[Part(text="I have 15 chestnuts. Joe ate 3. How many do I have left?")]),
    ]
    for msg in assistant_tool_messages:
        parts = []
        for p in msg["parts"]:
            if "functionCall" in p:
                parts.append(Part(function_call=p["functionCall"]))
            elif "functionResponse" in p:
                parts.append(Part(function_response=p["functionResponse"]))
        history.append(Content(role=msg["role"], parts=parts))

    second_response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=history,
    )

    print(second_response.text)
```

## See Also

- [Gemini Function Calling Documentation](https://ai.google.dev/gemini-api/docs/function-calling)
- [Architecture Overview](../../architecture/overview.md) — how ToolRegistry generates multi-provider schemas via llm-rosetta
