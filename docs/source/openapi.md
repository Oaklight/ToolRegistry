# OpenAPI Tool Usage Guide

## Introduction

This guide explains how to integrate OpenAPI with ToolRegistry, allowing you to register and call tools based on an OpenAPI specification. The guide provides examples for both synchronous and asynchronous registration methods, using a math service as a demonstration.

## OpenAPI Tool Registration

### Synchronous Registration

You can register OpenAPI tools synchronously using the `register_openapi_tools` method. For example:

```python
import os
from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)  # Default port is 8000; can be overridden by an environment variable
registry = ToolRegistry()
spec_url = f"http://localhost:{PORT}"

# Synchronously register OpenAPI tools
registry.register_openapi_tools(spec_url)
print(registry)  # Output: A ToolRegistry object with the registered OpenAPI tools
```

### Asynchronous Registration

In an asynchronous environment, use the `register_openapi_tools_async` method to register tools:

```python
import asyncio
import os
from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)
registry = ToolRegistry()
spec_url = f"http://localhost:{PORT}"

async def async_register():
    await registry.register_openapi_tools_async(spec_url)
    print(registry)  # Optionally, inspect the registry for registered tools

asyncio.run(async_register())
```

## Calling OpenAPI Tools

Once the OpenAPI tools are registered, they support both synchronous and asynchronous invocation methods.

### Synchronous Calls

Tools can be invoked directly as Python callables, or you can retrieve them using the `get_callable` or `get_tool` methods:

```python
# Direct access using subscript notation
add_func = registry["add"]
result = add_func(1, 2)
print(result)  # Expected output: 3

# Retrieve the callable with get_callable and call it
add_func = registry.get_callable("add")
result = add_func(3, 4)
print(result)  # Expected output: 7

# Retrieve the tool object with get_tool and invoke its run method
add_tool = registry.get_tool("add")
result = add_tool.run({"a": 5, "b": 6})
print(result)  # Expected output: 11
```

### Asynchronous Calls

For asynchronous calls, you can use the tool object's `__call__` or `arun` methods:

```python
import asyncio

async def call_async_add_func():
    # Retrieve the tool callable for asynchronous invocation
    add_func = registry.get_callable("add")
    result = await add_func(7, 7)
    print(result)  # Expected output: 14

    # Direct subscript access for asynchronous invocation
    add_func2 = registry["add"]
    result = await add_func2(7, 8)
    print(result)  # Expected output: 15

asyncio.run(call_async_add_func())

async def call_async_add_tool():
    # Retrieve the tool object for asynchronous invocation
    add_tool = registry.get_tool("add")
    result = await add_tool.arun({"a": 9, "b": 10})
    print(result)  # Expected output: 19

asyncio.run(call_async_add_tool())
```

## Integrating OpenAPI with the OpenAI Client

You can integrate OpenAPI tool registration into an OpenAI-compatible API workflow. The following example demonstrates how to load environment variables, register OpenAPI tools, and supply the tool JSON schema to the OpenAI client's chat completion interface.

```python
import os
import asyncio
from pprint import pprint
from dotenv import load_dotenv
from openai import OpenAI
from toolregistry import ToolRegistry

# Load environment variables from the .env file
load_dotenv()

PORT = os.getenv("PORT", 8000)
registry = ToolRegistry()
spec_url = f"http://localhost:{PORT}"

# Asynchronously register OpenAPI tools
async def async_register():
    await registry.register_openapi_tools_async(spec_url)
    pprint(registry)

asyncio.run(async_register())

# Set up the OpenAI client
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

# Make the chat completion request with the tool JSON schema
response = client.chat.completions.create(
    model="deepseek-v3",
    messages=messages,
    tools=registry.get_tools_json(),
    tool_choice="auto",
)

# If the model makes tool calls, process them
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
    print(tool_calls)

    # Execute the tool calls
    tool_responses = registry.execute_tool_calls(tool_calls)
    print(tool_responses)

    # Construct assistant messages with the tool call results
    assistant_tool_messages = registry.recover_tool_call_assistant_message(tool_calls, tool_responses)
    print(assistant_tool_messages)

    messages.extend(assistant_tool_messages)

    # Send the updated messages back to the model
    second_response = client.chat.completions.create(
        model="deepseek-v3", messages=messages
    )
    print(second_response.choices[0].message.content)
```

## Notes

1. OpenAPI tool registration supports both synchronous and asynchronous methods. Once tools are registered, they can be invoked as simple Python functions or as tool objects.
2. During invocation, parameters are automatically converted based on the tool definition. For example, the `add` tool expects numeric inputs and returns a numeric result.
3. The logging output during registration helps to verify the connection to the OpenAPI spec server and the retrieval of tool definitions.
4. The integration with the OpenAI client allows you to seamlessly incorporate tool execution into your chat workflows.

Follow the examples above to efficiently integrate and utilize OpenAPI tools with ToolRegistry.

---
