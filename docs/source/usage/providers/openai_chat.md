# OpenAI Chat Completion Integration

Following our simple math example from the [Basic Usage](../basics), this document explains how to use a tool registry with the OpenAI Chat Completion API. Note that you can use the OpenAI client with any API provider that offers OpenAI-compatible APIs. In this guide, we'll use DeepSeek as an example.

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
schemas = registry.get_tools_json(api_format="openai") # since it was the only format for openai for a long time
schemas = registry.get_tools_json(api_format="openai-chatcompletion") # to be explicit
```

Either of the above will return the tool schemas in the format required by the OpenAI Chat Completion API. Here is the indented JSON output:

```json
[
  {
    "type": "function",
    "function": {
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
      }
    }
  },
  {
    "type": "function",
    "function": {
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
      }
    }
  }
]
```

## Supply Query with Tool Schema

Provide the tool JSON schema to the OpenAI client's chat completion interface:

```python
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from the .env file
load_dotenv()

# Configure the OpenAI client
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
# Send the chat completion request
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=schemas, # this is where we feed in the schema
    tool_choice="auto",
)
```

## Extract Tool Calls

If the model (LLM) decides to use a tool, it will return `tool_calls` as part of the response message:

```python
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
```

Example function call output:

```python
[ChatCompletionMessageToolCall(id='call_egkg4evbb19d8012bex83v8a', function=Function(arguments='{"a":15,"b":3}', name='subtract'), type='function', index=0)]
```

The `tool_calls` object is a `List` of `ChatCompletionMessageToolCall` objects. The following attributes are particularly useful:

- `id`: this is something we will need when feed result back to LLM
- **`function`**: **this is the core, with arguments and name of target function**
- `index`: less useful in non-stream mode, but if you stream the chat result, this is the key to put together complete tool_calls information.

## Execute Tool Calls

Using the `ToolRegistry`, you can easily process results from **all** `tool_calls`. Note that sometimes the LLM may decide to call multiple tools simultaneously.

```python
# Execute tool calls
tool_responses = registry.execute_tool_calls(tool_calls)
```

The tool execution results from the registry are returned as a Python dictionary mapping `tool_call_id` to results:

```json
{ "call_0_bfa567b8-2f10-4113-953a-56e87b664e0f": 12 }
```

## Feed Results back to LLM

After executing the tool calls, we still need to inform the LLM about the results before it can answer the original question.

To maintain the tool-calling context for subsequent LLM interactions, we need to reconstruct both:

1. The assistant's decision to make `tool_calls`
2. The actual `tool_calls` results

```python
# Construct assistant messages with results
assistant_tool_messages = registry.recover_tool_call_assistant_message(
    tool_calls, tool_responses, api_format="openai-chatcompletion" # or "openai"
) # you can leave out api_format, it defaults to "openai-chatcompletion"
```

```json
[
  {
    "content": null,
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_wAcYzTLh37jfrCmihEv7x4FC",
        "function": {
          "arguments": "{\"a\":15,\"b\":3}",
          "name": "subtract"
        },
        "type": "function"
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_wAcYzTLh37jfrCmihEv7x4FC",
    "content": "12"
  }
]
```

We then extend the previous messages sent to first LLM with these reconstructed messages.

```python
messages.extend(assistant_tool_messages)

# Send the results back to the model
second_response = client.chat.completions.create(
    model="deepseek-chat", messages=messages
)

# Print final response
print(second_response.choices[0].message.content)
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

model_name = os.getenv("MODEL", "deepseek-chat")
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
response = client.chat.completions.create(
    model=model_name,
    messages=messages,
    tools=registry.get_tools_json(api_format="openai-chatcompletion"),
    tool_choice="auto",
)

# Handle tool calls using ToolRegistry
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
    print(tool_calls)

    # Execute tool calls
    tool_responses = registry.execute_tool_calls(tool_calls)
    print(tool_responses)

    # Construct assistant messages with results
    assistant_tool_messages = registry.recover_tool_call_assistant_message(
        tool_calls, tool_responses, api_format="openai-chatcompletion"
    )
    print(json.dumps(assistant_tool_messages, indent=2))

    # Send the results back to the model
    messages.extend(assistant_tool_messages)
    second_response = client.chat.completions.create(
        model=model_name, messages=messages
    )

    # Print final response
    print(second_response.choices[0].message.content)
```
