# OpenAPI Tool Usage Guide

```{note}
API updates in version: 0.4.12
New in version: 0.4.0
```

## Introduction

This guide explains how to integrate OpenAPI with ToolRegistry, allowing you to register and call tools based on an OpenAPI specification. The guide provides examples for both synchronous and asynchronous registration methods, using a math service as a demonstration.

## API Changes in version 0.4.12

The `register_from_openapi` method now accepts two parameters:

- `client_config`: a `toolregistry.openapi.HttpxClientConfig` object that configures the HTTP client used to interact with the API. You can configure the headers, authorization, timeout, and other settings. Allowing greater flexibility than the previous version.
- `openapi_spec`: The OpenAPI specification as `Dict[str, Any]`, loaded with a function like `load_openapi_spec` or `load_openapi_spec_async`. These functions accept a file path or a URL to the OpenAPI specification or a URL to the base api and return the parsed OpenAPI specification as a dictionary.

You must now explicitly pass both the `client_config` and `openapi_spec` arguments.

## OpenAPI Tool Registration

### Synchronous Registration

You can register OpenAPI tools synchronously using the `register_from_openapi` method. For example:

```python
import os
from toolregistry.openapi import HttpxClientConfig, load_openapi_spec
from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)  # Default port is 8000; can be overridden by an environment variable
registry = ToolRegistry()
client_config = HttpxClientConfig(base_url=f"http://localhost:{PORT}")
openapi_spec = load_openapi_spec("http://localhost:{PORT}")  # Auto-discovery of OpenAPI spec

# Synchronously register OpenAPI tools
registry.register_from_openapi(client_config=client_config, openapi_spec=openapi_spec)
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
from toolregistry.openapi import HttpxClientConfig, load_openapi_spec_async
from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)
registry = ToolRegistry()
client_config = HttpxClientConfig(base_url=f"http://localhost:{PORT}")

async def async_register():
    openapi_spec = await load_openapi_spec_async("http://localhost:{PORT}")  # Auto-discovery of OpenAPI spec
    await registry.register_from_openapi_async(client_config=client_config, openapi_spec=openapi_spec)
    print(registry)  # Optionally, inspect the registry for registered tools

asyncio.run(async_register())
```

### Httpx Client Configuration

In some cases, OpenAPI services may require specific configurations such as custom headers, timeouts, or SSL certificates. You can tune these settings with the `HttpxClientConfig` class. Here's an example of authorization bearer tokens in header.

```python
from toolregistry.openapi import HttpxClientConfig

OPENAPI_SERVER_URL = os.getenv("OPENAPI_SERVER_URL", "http://localhost:8000")
OPENAPI_BEARER_TOKENS = os.getenv("OPENAPI_BEARER_TOKENS", "your-api-token")

client_config = HttpxClientConfig(
    base_url=OPENAPI_SERVER_URL,
    headers={"Authorization": f"Bearer {OPENAPI_BEARER_TOKENS}"}, # this sets the Bearer token
)
```

If nothing special is needed, you can create HttpxClientConfig with just the `base_url`:

```python
from toolregistry.openapi import HttpxClientConfig

client_config = HttpxClientConfig(
    base_url=OPENAPI_SERVER_URL,
)
```

### Load OpenAPI Specification

When using the functions `load_openapi_spec` or `load_openapi_spec_async`, the following behaviors apply:

1. **Base URL provided**: If you specify only a base URL (e.g., `http://localhost:8000`), the loader will attempt "best effort" auto-discovery to locate the OpenAPI specification file. It checks endpoints such as `http://<base_url>/openapi.json`, `http://<base_url>/swagger.json`, etc. If auto-discovery fails, ensure the base URL is accurate and the specification is accessible.
2. **File path provided**: If you provide a file path (e.g., `./openapi_spec.json`), the function will load the OpenAPI specification directly from the file. Unlike simple direct load, the functionality includes unwinding `$ref` blocks commonly found in OpenAPI specifications. This ensures that any schema references are fully resolved within the returned dictionary.

```python
from toolregistry.openapi import load_openapi_spec

openapi_spec = load_openapi_spec("./openapi_spec.json") # Load from file
openapi_spec = load_openapi_spec("http://localhost:8000") # auto-discovery with URL to service root
openapi_spec = load_openapi_spec("http://localhost:8000/openapi.json") # load from specification URL
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

You can integrate OpenAPI tool registration into an OpenAI-compatible API workflow. The updated example incorporates the new APIs:

```python
from dotenv import load_dotenv
from toolregistry.openapi import HttpxClientConfig, load_openapi_spec
from toolregistry import ToolRegistry
from openai import OpenAI
import os

# Load environment variables from .env file
load_dotenv()
PORT = os.getenv("PORT", 8000)  # default port 8000, change via environment variable

registry = ToolRegistry()
client_config = HttpxClientConfig(base_url=f"http://localhost:{PORT}")
openapi_spec = load_openapi_spec(f"http://localhost:{PORT}")
registry.register_from_openapi(client_config=client_config, openapi_spec=openapi_spec)

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
