# MCP Tool Usage Guide

## Introduction

This guide explains how to integrate MCP (Modular Component Protocol) with ToolRegistry, allowing you to register and call tools from an MCP server. To simplify the developer's work, this guide provides examples for both synchronous and asynchronous calls, using a math service as a demonstration.

## MCP Tool Registration

### Synchronous Registration

You can register MCP tools synchronously using the `register_mcp_tools` method. For example:

```python
import os
from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)  # Default port is 8000; can be overridden by environment variable
registry = ToolRegistry()
mcp_server_url = f"http://localhost:{PORT}/mcp/sse"

# Synchronously register MCP tools
registry.register_mcp_tools(mcp_server_url)
print(registry)  # Output: A ToolRegistry object containing the registered MCP tools
```

### Asynchronous Registration

In an asynchronous environment, use the `register_mcp_tools_async` method to register tools. For example:

```python
import asyncio
import os
from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)
registry = ToolRegistry()
mcp_server_url = f"http://localhost:{PORT}/mcp/sse"

async def async_register():
    await registry.register_mcp_tools_async(mcp_server_url)
    # Optional: Use pprint to display the registered tools information
    # from pprint import pprint
    # pprint(registry)

asyncio.run(async_register())
```

## Calling MCP Tools

Once registered, MCP tools support both synchronous and asynchronous calling methods. Below are examples for each.

### Synchronous Calls

Tools can be called directly as Python callables or obtained through the `get_callable` or `get_tool` methods:

```python
# Directly call the tool using subscript access (__getitem__)
add_func = registry["add"]
result = add_func(1, 2)
print(result)  # Output: 3

# Get the tool function using get_callable and call it
add_func = registry.get_callable("add")
result = add_func(3, 4)
print(result)  # Output: 7

# Get the tool object using get_tool and call its run method
add_tool = registry.get_tool("add")
result = add_tool.run({"a": 5, "b": 6})
print(result)  # Output: 11
```

### Asynchronous Calls

For asynchronous calls, use the tool object's `__acall__` or `arun` methods. For example:

```python
import asyncio

async def call_async_add_func():
    # Use get_callable to obtain the tool function for asynchronous invocation
    add_func = registry.get_callable("add")
    result = await add_func.__acall__(7, 7)
    print(result)  # Output: 14

    # Directly access the tool function using subscript (__getitem__)
    add_func2 = registry["add"]
    result = await add_func2.__acall__(7, 8)
    print(result)  # Output: 15

asyncio.run(call_async_add_func())

async def call_async_add_tool():
    # Get the tool object using get_tool for asynchronous invocation
    add_tool = registry.get_tool("add")
    result = await add_tool.arun({"a": 9, "b": 10})
    print(result)  # Output: 19

asyncio.run(call_async_add_tool())
```

## Notes

1. MCP tool registration supports both synchronous and asynchronous methods. Once registered, tools can be called directly or used as tool objects.
2. During calls, parameters are automatically converted based on the tool definition. For instance, the `add` tool expects integer parameters and returns an integer.
3. The logging output during registration helps determine the MCP server connection status and tool retrieval status.

Follow the examples above to easily integrate and call MCP tools in your project.

---

## Integrating MCP with OpenAI

The following section extends the MCP tool usage guide by demonstrating how to use MCP tools within an OpenAI-compatible API workflow. This example is inspired by the code in `examples/openai_toolregistry_mcp_math.py` and follows a similar style to the [Function Calling](openai.md) document.

### Set Up OpenAI Client and Supply Tool Schema

First, load environment variables and set up the ToolRegistry as well as the OpenAI client. Then, obtain the tool JSON schema from the registry and supply it to the OpenAI client's chat completion interface.

```python
import os
import asyncio
from pprint import pprint
from dotenv import load_dotenv
from openai import OpenAI
from toolregistry import ToolRegistry

# Load environment variables from the .env file
load_dotenv()

PORT = os.getenv("PORT", 8000)  # Default port is 8000; can be overridden by environment variable

registry = ToolRegistry()
mcp_server_url = f"http://localhost:{PORT}/mcp/sse"

# Asynchronously register MCP tools
async def async_register():
    await registry.register_mcp_tools_async(mcp_server_url)
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

# Send the chat completion request with the tool schema
response = client.chat.completions.create(
    model="deepseek-v3",
    messages=messages,
    tools=registry.get_tools_json(),  # Supply the MCP tool JSON schema
    tool_choice="auto",
)
```

### Understanding `tool_calls`

If the model decides to use a tool, the response will include `tool_calls` in the message. You can inspect these calls as follows:

```python
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
    print(tool_calls)
```

For example, the output might look like this:

```python
[ChatCompletionMessageToolCall(id='call_xyz', function=Function(arguments='{"a":15,"b":3}', name='subtract'), type='function', index=0)]
```

### Executing Tool Calls

Using the ToolRegistry, execute the tool calls returned by the model:

```python
# Execute the tool calls
tool_responses = registry.execute_tool_calls(tool_calls)
print(tool_responses)
```

The results are returned as a dictionary mapping tool call IDs to their corresponding outputs.

### Feeding Results Back to the LLM

After executing the tool calls, construct assistant messages that include the tool results. This helps the LLM understand the context and generate the final answer.

```python
# Construct assistant messages with the tool call results
assistant_tool_messages = registry.recover_tool_call_assistant_message(tool_calls, tool_responses)
print(assistant_tool_messages)

# Extend the conversation with these messages
messages.extend(assistant_tool_messages)

# Send the updated messages back to the model
second_response = client.chat.completions.create(
    model="deepseek-v3", messages=messages
)

# Print the final response from the model
print(second_response.choices[0].message.content)
```

### Complete Python Script

Below is the complete script integrating MCP with OpenAI:

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
mcp_server_url = f"http://localhost:{PORT}/mcp/sse"

# Asynchronously register MCP tools
async def async_register():
    await registry.register_mcp_tools_async(mcp_server_url)
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

# Make the chat completion request with MCP tools
response = client.chat.completions.create(
    model="deepseek-v3",
    messages=messages,
    tools=registry.get_tools_json(),
    tool_choice="auto",
)

# If tool calls are made, process them
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
    print(tool_calls)

    # Execute tool calls
    tool_responses = registry.execute_tool_calls(tool_calls)
    print(tool_responses)

    # Construct assistant messages with tool results
    assistant_tool_messages = registry.recover_tool_call_assistant_message(tool_calls, tool_responses)
    print(assistant_tool_messages)

    messages.extend(assistant_tool_messages)

    # Send the updated conversation back to the model
    second_response = client.chat.completions.create(
        model="deepseek-v3", messages=messages
    )

    # Print the final answer
    print(second_response.choices[0].message.content)
```

### Final Result

The LLM will process the tool execution results and return the final answer, which in this example should indicate the number of chestnuts remaining.

---

This extended section demonstrates how MCP tools can be integrated and utilized with an OpenAI-compatible API in a tool-assisted chat workflow.
