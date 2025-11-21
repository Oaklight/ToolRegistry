# MCP Tool Usage Guide

```{note}
New in version: 0.3.0
```

## Introduction

This guide explains how to integrate MCP (Model Context Protocol) with ToolRegistry, enabling registration and invocation of tools from an MCP server. It provides example workflows for synchronous and asynchronous calls, using a math service as a demonstration.

## Supported Transport and Input Types

The MCP integration supports flexible transport options:

- **Web-based Transports**:
  - `Streamable Http` (e.g., `http://localhost:8000/mcp`)
  - `SSE` (e.g., `http://localhost:8000/mcp/sse`)
  - `WebSocket` (e.g., `ws://localhost:8000/mcp`)
- **Stdio Transport**:
  - Script file paths (e.g., `.py`, `.js`)
  - Config-based setup
- **FastMCP Transport**:
  - Pythonic instances of
    - FastMCP 2.x servers
    - FastMCP 1.x servers from the `mcp.server.fastmcp` package
  
Supported inputs include URLs (`http://`, `https://`, `ws://`), script paths, client transport instances, or FastMCP objects. We will demonstrate in [registration example](#registration-synchronous) below.

```{note}
Starting with [`MCP 2025-03-26`](https://modelcontextprotocol.io/specification/2025-03-26/changelog) and [`fastmcp 2.3.0`](https://gofastmcp.com/clients/transports#streamable-http), `http+sse` transport has been replaced by `streamable http`. Since **`toolregistry 0.4.7`**, this transport is supported with fallback for legacy `http+sse`. 

It's recommended to update your MCP servers to use `streamable http` for optimal performance, as future versions may phase out `http+sse`.
```

## Usage

### Registration (synchronous)

To register MCP tools synchronously, use the `register_from_mcp` method with various transport options:

```python

from pathlib import Path
from fastmcp.client.transports import FastMCP, StreamableHttpTransport
from toolregistry import ToolRegistry

registry = ToolRegistry()

# Example transports for registration:
transport = "https://mcphub.url/mcp"  # mcp streamable http
transport = "http://localhost:8000/sse/test_group"  # mcp http+sse
transport = "examples/mcp_related/mcp_servers/math_server.py"  # Path to mcp server script
transport = {
    "mcpServers": {
        "make_mcp": {
            "command": f"{Path.home()}/mambaforge/envs/toolregistry_dev/bin/python",
            "args": [
                f"{Path.home()}/projects/toolregistry/examples/mcp_related/mcp_servers/math_server.py"
            ],
            "env": {},
        }
    }
} # Example mcp configuration dict
transport = FastMCP(name="MyFastMCP")  # naive FastMCP instance
transport = StreamableHttpTransport(url="https://mcphub.example.com/mcp", headers={"Authorization": "Bearer token"})  # Transport instance, useful if you have custom headers

# Register tools synchronously
registry.register_from_mcp(transport)

print(registry)  # Outputs registered tools
```

```{tip}
`ToolRegistry.register_from_mcp` supports URLs or paths, which are sufficient for most scenarios. For advanced needs, like custom headers, use a transport instance (e.g., `StreamableHttpTransport`) with specific configurations.
```

```{tip}
Emerging MCP hub services, commercial or self-hosted, simplify discovering and centralizing MCP servers. They’re ideal for avoiding stdio servers, reducing environment clutter, or enabling MCP host sharing.
```

### Calling MCP Tools (synchronous)

Registered tools can be invoked synchronously using subscript notation access, callable methods, or `.run()` methods:

```python
# Calling a tool using subscript notation
result = registry["add"](1, 2)
print(result)  # Output: 3

# Using get_callable
add_func = registry.get_callable("add")
result = add_func(3, 4)
print(result)  # Output: 7

# Using get_tool and its .run() method
add_tool = registry.get_tool("add")
result = add_tool.run({"a": 5, "b": 6})
print(result)  # Output: 11
```

## Sync vs Async Usability

MCP integration supports both synchronous and asynchronous workflows, catering to varied developer needs. While MCP clients are inherently asynchronous, the integration provides both synchronous and asynchronous interfaces for convenience:

- **Synchronous**: Best suited for single-threaded environments or simple scripts. It wraps the inherently asynchronous workflows into a synchronous interface for ease of use.

- **Asynchronous**: Ideal for event-driven frameworks or scenarios requiring concurrent communication with multiple servers, ensuring non-blocking operations and scalability.

### Asynchronous Registration of MCP Tools

For asynchronous environments, use the `register_from_mcp_async` method:

```python
import asyncio
from toolregistry import ToolRegistry
from fastmcp.client.transports import FastMCP

registry = ToolRegistry()
transport = "http://localhost:8000/mcp"  # Example transport URL
fastmcp_server = FastMCP(name="MyFastMCP")  # FastMCP instance

async def async_register():
    await registry.register_from_mcp_async(transport)

asyncio.run(async_register())
```

### Asynchronous Tool Calls

Tools can also be invoked asynchronously using their `__call__()` or `arun()` methods:

```python
import asyncio

async def call_async_add_func():
    add_func = registry.get_callable("add")
    result = await add_func(7, 7)
    print(result)  # Output: 14

async def call_async_add_tool():
    add_tool = registry.get_tool("add")
    result = await add_tool.arun({"a": 9, "b": 10})
    print(result)  # Output: 19

asyncio.run(call_async_add_func())
asyncio.run(call_async_add_tool())
```

## Integrating MCP with OpenAI Client

Enhance OpenAI workflows by registering MCP tools in ToolRegistry, providing tool schemas for automated execution during chat completions.

### Setting Up OpenAI Client and MCP Tool Registration

```python
import os
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
from toolregistry import ToolRegistry

load_dotenv()
PORT = os.getenv("PORT", 8000)

# Register MCP tools asynchronously
registry = ToolRegistry()
mcp_server_url = f"http://localhost:{PORT}/sse"

async def async_register():
    await registry.register_from_mcp_async(mcp_server_url)

asyncio.run(async_register())

# Set up the OpenAI client
client = OpenAI(
    api_key=os.getenv("API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.deepseek.com/")
)

messages = [{"role": "user", "content": "I have 15 chestnuts. Joe ate 3. How many chestnuts do I have left?"}]

# Make chat completion request using MCP tools
response = client.chat.completions.create(
    model="deepseek-chat", messages=messages, tools=registry.get_tools_json(), tool_choice="auto"
)
```

### Executing Tool Calls and Feeding Results Back

If the model decides to use MCP tools, extract `tool_calls` and execute them automatically:

```python
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
    
    # Execute tool calls
    tool_responses = registry.execute_tool_calls(tool_calls)

    # Construct assistant messages and extend conversation
    assistant_tool_messages = registry.recover_tool_call_assistant_message(tool_calls, tool_responses)
    messages.extend(assistant_tool_messages)

    # Feed updated messages back to the model
    second_response = client.chat.completions.create(
        model="deepseek-chat", messages=messages
    )

    print(second_response.choices[0].message.content)
```

### Final Output

The LLM will process results from MCP tools and respond accordingly, completing the query.
