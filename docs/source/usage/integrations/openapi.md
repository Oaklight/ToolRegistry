# OpenAPI Tool Usage Guide

```{note}
New in version: 0.4.0
```

## Introduction

This guide explains how to integrate OpenAPI with ToolRegistry, allowing you to register and call tools based on an OpenAPI specification. The guide provides examples for both synchronous and asynchronous registration methods, using a math service as a demonstration.

## OpenAPI Tool Registration

### Synchronous Registration

You can register OpenAPI tools synchronously using the `register_from_openapi` method. For example:

```python
import os
from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)  # Default port is 8000; can be overridden by an environment variable
registry = ToolRegistry()
spec_url = f"http://localhost:{PORT}"

# Synchronously register OpenAPI tools
registry.register_from_openapi(spec_url)
print(registry)  # Output: A ToolRegistry object with the registered OpenAPI tools
```

You should see a schema printed as follow. Here, we only display the first entry for clarity.

```json
[
  {
    "type": "function",
    "function": {
      "name": "add_get",
      "description": "Calculate a + b and return the result.\n\nArgs:\n    a (float): The first operand.\n    b (float): The second operand.\n\nReturns:\n    dict: A dictionary containing the key \"result\" with the sum of a and b.",
      "parameters": {
        "type": "object",
        "properties": {
          "a": {
            "type": "number",
            "description": ""
          },
          "b": {
            "type": "number",
            "description": ""
          }
        },
        "required": ["a", "b"]
      },
      "is_async": false
    }
  }
]
```

### Asynchronous Registration

In an asynchronous environment, use the `register_from_openapi_async` method to register tools:

```python
import asyncio
import os
from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)
registry = ToolRegistry()
spec_url = f"http://localhost:{PORT}"

async def async_register():
    await registry.register_from_openapi_async(spec_url)
    print(registry)  # Optionally, inspect the registry for registered tools

asyncio.run(async_register())
```

## Calling OpenAPI Tools

Once the OpenAPI tools are registered, they support both synchronous and asynchronous invocation methods.

### Synchronous Calls

Tools can be invoked directly as Python callables, or you can retrieve them using the `get_callable` or `get_tool` methods:

```python
# Direct access using subscript notation
add_func = registry["add_get"]
result = add_func(1, 2)
print(result)  # Expected output: 3.0

# Retrieve the callable with get_callable and call it
add_func = registry.get_callable("add_get")
result = add_func(3, 4)
print(result)  # Expected output: 7.0

# Retrieve the tool object with get_tool and invoke its run method
add_tool = registry.get_tool("add_get")
result = add_tool.run({"a": 5, "b": 6})
print(result)  # Expected output: 11.0
```

### Asynchronous Calls

For asynchronous calls, you can use the tool object's `__call__` or `arun` methods:

```python
import asyncio

async def call_async_add_func():
    # Retrieve the tool callable for asynchronous invocation
    add_func = registry.get_callable("add_get")
    result = await add_func(7, 7)
    print(result)  # Expected output: 14.0

    # Direct subscript access for asynchronous invocation
    add_func2 = registry["add_get"]
    result = await add_func2(7, 8)
    print(result)  # Expected output: 15.0

asyncio.run(call_async_add_func())

async def call_async_add_tool():
    # Retrieve the tool object for asynchronous invocation
    add_tool = registry.get_tool("add_get")
    result = await add_tool.arun({"a": 9, "b": 10})
    print(result)  # Expected output: 19.0

asyncio.run(call_async_add_tool())
```

## Integrating OpenAPI with the OpenAI Client

You can integrate OpenAPI tool registration into an OpenAI-compatible API workflow. The following example demonstrates how to load environment variables, register OpenAPI tools, and supply the tool JSON schema to the OpenAI client's chat completion interface.

```python
import asyncio
import os
from pprint import pprint

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry

# Load environment variables from .env file
load_dotenv()


PORT = os.getenv("PORT", 8000)  # default port 8000, change via environment variable

registry = ToolRegistry()

spec_url = f"http://localhost:{PORT}"

registry.register_from_openapi(spec_url)
pprint(registry)


async def async_register():
    await registry.register_from_openapi_async(spec_url)
    pprint(registry)


asyncio.run(async_register())

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
    model="deepseek-v3",
    messages=messages,
    tools=registry.get_tools_json(),
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
        tool_calls, tool_responses
    )
    print(assistant_tool_messages)

    # Send the results back to the model
    messages.extend(assistant_tool_messages)
    second_response = client.chat.completions.create(
        model="deepseek-v3", messages=messages
    )

    # Print final response
    print(second_response.choices[0].message.content)
```

## Notes

1. OpenAPI tool registration supports both synchronous and asynchronous methods. Once tools are registered, they can be invoked as simple Python functions or as tool objects.
2. During invocation, parameters are automatically converted based on the tool definition. For example, the `add_get` tool expects numeric inputs and returns a numeric result.
3. The integration with the OpenAI client allows you to seamlessly incorporate tool execution into your chat workflows.

Follow the examples above to efficiently integrate and utilize OpenAPI tools with ToolRegistry.
