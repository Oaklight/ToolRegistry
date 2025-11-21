# OpenAI Response API Integration

Following our simple math example from the [Basic Usage](../basics), this document explains how to use a tool registry with the OpenAI Response API. Note that you could use the OpenAI client with any API provider that offers OpenAI-Response API. In this guide, we'll use OpenAI as an example.

## Setup ToolRegistry

We have a tool registry with two math functions:

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
schemas = registry.get_tools_json(api_format="openai-response") # available since v0.4.13
```

Here is the pretty printed JSON schema:

```json
[
  {
    "type": "function",
    "name": "add",
    "description": "Add two numbers together.",
    "parameters": {
      "properties": {
        "a": {
          "title": "A",
          "type": "number"
        },
        "b": {
          "title": "B",
          "type": "number"
        }
      },
      "required": [
        "a",
        "b"
      ],
      "title": "addParameters",
      "type": "object"
    },
    "strict": false
  },
  {
    "type": "function",
    "name": "subtract",
    "description": "Subtract the second number from the first.",
    "parameters": {
      "properties": {
        "a": {
          "title": "A",
          "type": "integer"
        },
        "b": {
          "title": "B",
          "type": "integer"
        }
      },
      "required": [
        "a",
        "b"
      ],
      "title": "subtractParameters",
      "type": "object"
    },
    "strict": false
  }
]
```

Note the difference:

- The `openai-response` function tool format exposes the function information (`name`, `description`, `parameters`) as top-level objects, instead of nested inside a `function` object.
- There is a `strict` field that is set to `false`. Do NOT change this value, since in strict mode, all optional parameters will be required, which is not the desired behavior for automatic schema generation.

## Supply Query with Tool Schema

Provide the tool JSON schema and user query to the OpenAI client's completion interface:

```python
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from the .env file
load_dotenv()

# Configure the OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.openai.com/v1/"),
)

messages = [
    {
        "role": "user",
        "content": "I have 15 chestnuts. Joe ate 3. How many chestnuts do I have left?",
    }
]

# Make the chat completion request
response = client.responses.create(
    model="gpt-4.1-mini",
    input=messages,
    tools=schemas, # Pass the tool schemas here
    tool_choice="auto",
)
```

## Extract Tool Calls

If the model decides to use a tool, it will return a response type of `function_call`. Extract this information from the response:

```python
tool_calls = []
for each in response.output:
    if each.type == "function_call":
        tool_calls.append(each)
```

Example function call output:

```python
[ResponseFunctionToolCall(arguments='{"a":15,"b":3}', call_id='call_FbBTgiYFPuLwdk6jNW2JaNQh', name='subtract', type='function_call', id='fc_6855102fc05c819ba4583b9cb0b6b73b07c0143154471823', status='completed')]
```

The `tool_calls` object is a `List` of `ResponseFunctionToolCall` objects. The following attributes are particularly useful:

- `call_id`: this is something we will need when feed result back to LLM
- **`name`**: The name of the function to call
- **`arguments`**: A dictionary of arguments to pass to the function

## Execute Tool Calls

Using the `ToolRegistry`, you can easily process results from **all** `tool_calls`. Note that sometimes the LLM may decide to call multiple tools simultaneously.

```python
# Execute tool calls
tool_responses = registry.execute_tool_calls(tool_calls)
```

The tool execution results from the registry are returned as a Python dictionary mapping `tool_call_id` to results:

```json
{ "call_FbBTgiYFPuLwdk6jNW2JaNQh": 12 }
```

## Feed Results back to LLM

After executing the function call, we need to provide the result back to the model in a new prompt:

To maintain the tool-calling context for subsequent LLM interactions, we need to reconstruct both:

1. The assistant's decision to make `tool_calls`
2. The actual `tool_calls` results

```python
# Construct assistant messages with results
assistant_tool_messages = registry.recover_tool_call_assistant_message(
    tool_calls, tool_responses, api_format="openai-response"
)
```

```json
[
  {
    "arguments": "{\"a\":15,\"b\":3}",
    "call_id": "call_A8O8pkZJGgZlGrcF3nhxv7II",
    "name": "subtract",
    "type": "function_call",
    "id": null,
    "status": null
  },
  {
    "type": "function_call_output",
    "call_id": "call_A8O8pkZJGgZlGrcF3nhxv7II",
    "output": "12"
  }
]
```

We then extend the previous messages sent to first LLM with these reconstructed messages.

```python
messages.extend(assistant_tool_messages)

# Send the results back to the model
response = client.responses.create(
    model="gpt-4.1-mini",
    input=messages,
    tools=registry.get_tools_json(api_format="openai-response"),
    tool_choice="auto",
)

# Print final response
if response.output:
    print(response.output_text)
```

## Final Result and Considerations

The LLM will return the final answer after processing the tool execution results:

```markdown
You have **12 chestnuts** left after Joe ate 3.
```

### Important Implementation Notes

The implementation should handle [consecutive function calls](../../examples/consecutive_tool_calls) as the conversation may require multiple rounds of tool calls, with each response from the LLM potentially triggering new tool calls.

Error handling is crucial; always validate tool call arguments before execution, as the ToolRegistry does this for you. Handle cases where tools might fail or return errors, and consider timeout mechanisms for long-running operations.

State management involves maintaining conversation history, including all tool calls and responses, tracking the sequence of tool executions for debugging, and considering conversation state persistence.

Performance considerations include minimizing unnecessary tool calls, caching frequent tool responses when appropriate, and monitoring and optimizing tool execution time.

## Complete Python Script

Here goes the complete script used in this demo.

```python
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry

# Load environment variables from .env file
load_dotenv()

model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

registry = ToolRegistry()


@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@registry.register
def subtract(a: int, b: int) -> int:
    """Subtract the second number from the first."""
    return a - b


print(json.dumps(registry.get_tools_json(api_format="openai-response"), indent=2))

# Set up OpenAI client
client = OpenAI(
    api_key=os.getenv("API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.deepseek.com/"),
)


messages = [
    {
        "role": "user",
        "content": "I have 15 chestnuts. Joe ate 3. How many chestnuts do I have left?",
    }
]

# Make the chat completion request
response = client.responses.create(
    model=model_name,
    input=messages,
    tools=registry.get_tools_json(api_format="openai-response"),
    tool_choice="auto",
)

tool_calls = []
for each in response.output:
    if each.type == "function_call":
        tool_calls.append(each)
print(tool_calls)

# Execute tool calls
tool_responses = registry.execute_tool_calls(tool_calls)
print(tool_responses)

# Construct assistant messages with results
assistant_tool_messages = registry.recover_tool_call_assistant_message(
    tool_calls, tool_responses, api_format="openai-response"
)
print(json.dumps(assistant_tool_messages, indent=2))

messages.extend(assistant_tool_messages)

# Send the results back to the model
response = client.responses.create(
    model=model_name,
    input=messages,
    tools=registry.get_tools_json(api_format="openai-response"),
    tool_choice="auto",
)

# Print final response
if response.output:
    print(response.output_text)
```
