# MCP 工具使用指南

???+ note "变更日志"
    新增于版本：0.3.0

## 简介

本指南介绍如何将 MCP（Model Context Protocol）与 ToolRegistry 集成，实现从 MCP 服务器注册和调用工具的功能。指南以数学服务为例，提供了同步和异步调用的示例工作流。

## 支持的传输方式和输入类型

MCP 集成支持灵活的传输选项：

- **基于 Web 的传输方式**：
    - `Streamable Http`（例如 `http://localhost:8000/mcp`）
    - `SSE`（例如 `http://localhost:8000/mcp/sse`）
    - `WebSocket`（例如 `ws://localhost:8000/mcp`）
- **Stdio 传输方式**：
    - 脚本文件路径（例如 `.py`、`.js`）
    - 基于配置的方式（包含 `command`、`args`、`env` 的字典）

支持的输入包括 URL 字符串（`http://`、`https://`、`ws://`、`wss://`）、脚本路径（`.py`、`.js`）或字典配置。我们将在下方的[注册示例](#registration-synchronous)中进行演示。

!!! note "MCP 客户端解耦"
    自 **`toolregistry 0.5.0`** 起，MCP 集成使用官方 [`mcp`](https://pypi.org/project/mcp/) SDK（`mcp>=1.0.0,<2.0.0`）替代了 `fastmcp`，从而减轻了依赖负担。`transport` 参数现在接受 `Union[str, Dict[str, Any], Path]` 类型——不再接受 `ClientTransport` 和 `FastMCP` 实例。

    公共 API（`register_from_mcp` / `register_from_mcp_async`）保持不变。

!!! note "MCP 传输方式更新"
    从 [`MCP 2025-03-26`](https://modelcontextprotocol.io/specification/2025-03-26/changelog) 开始，`http+sse` 传输方式已被 `streamable http` 取代。自 **`toolregistry 0.4.7`** 起，已支持该传输方式，并对旧版 `http+sse` 提供回退兼容。

    建议将你的 MCP 服务器升级为使用 `streamable http` 以获得最佳性能，因为未来版本可能会逐步淘汰 `http+sse`。

## 用法

### 注册（同步）

要同步注册 MCP 工具，请使用 `register_from_mcp` 方法，支持多种传输选项：

```python
from pathlib import Path
from toolregistry import ToolRegistry

registry = ToolRegistry()

# Example transports for registration:
transport = "https://mcphub.url/mcp"  # mcp streamable http
transport = "http://localhost:8000/sse/test_group"  # mcp http+sse
transport = "ws://localhost:8000/mcp"  # websocket
transport = "examples/mcp_related/mcp_servers/math_server.py"  # Path to mcp server script
transport = {
    "command": "python",
    "args": ["examples/mcp_related/mcp_servers/math_server.py"],
    "env": {},
}  # Stdio config dict

# Register tools synchronously
registry.register_from_mcp(transport)

print(registry)  # Outputs registered tools
```

!!! tip "提示"
    `ToolRegistry.register_from_mcp` 支持 URL 字符串、脚本路径和字典配置，可以满足大多数使用场景。

!!! tip "提示"
    新兴的 MCP Hub 服务（无论是商业的还是自托管的）简化了 MCP 服务器的发现和集中管理。它们非常适合避免使用 stdio 服务器、减少环境负担，或实现 MCP 主机共享。

### 调用 MCP 工具（同步）

已注册的工具可以通过下标访问、可调用方法或 `.run()` 方法进行同步调用：

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

## 同步与异步的适用场景

MCP 集成同时支持同步和异步工作流，以满足不同开发者的需求。虽然 MCP 客户端本质上是异步的，但集成提供了同步和异步两种接口以方便使用：

- **同步**：最适合单线程环境或简单脚本。它将本质上异步的工作流封装为同步接口，便于使用。

- **异步**：适用于事件驱动框架或需要与多个服务器并发通信的场景，确保非阻塞操作和可扩展性。

### 异步注册 MCP 工具

在异步环境中，使用 `register_from_mcp_async` 方法：

```python
import asyncio
from toolregistry import ToolRegistry

registry = ToolRegistry()
transport = "http://localhost:8000/mcp"  # Example transport URL

async def async_register():
    await registry.register_from_mcp_async(transport)

asyncio.run(async_register())
```

### 异步调用工具

工具也可以通过其 `__call__()` 或 `arun()` 方法进行异步调用：

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

## 持久连接

???+ note "变更日志"
    新增于版本：0.7.0

默认情况下，MCP 连接现在是**持久的**——与 MCP 服务器的连接在多次工具调用之间保持打开状态，避免了重复握手的开销。这由内部的 `MCPConnectionManager` 管理。

### 上下文管理器用法

使用 `ToolRegistry` 作为上下文管理器可确保连接被正确关闭：

```python
from toolregistry import ToolRegistry

# Synchronous
with ToolRegistry() as registry:
    registry.register_from_mcp("http://localhost:8000/mcp")
    result = registry["add"](1, 2)
# Connections are automatically closed on exit

# Asynchronous
async with ToolRegistry() as registry:
    await registry.register_from_mcp_async("http://localhost:8000/mcp")
    result = await registry["add"](1, 2)
# Connections are automatically closed on exit
```

### 显式清理

你也可以显式关闭连接：

```python
registry = ToolRegistry()
registry.register_from_mcp("http://localhost:8000/mcp")
# ... use tools ...
registry.close()  # Close all persistent connections

# Or in async code:
await registry.close_async()
```

### 退出持久连接模式

如果你倾向于每次调用都新建连接（旧行为），可以在注册时传递 `persistent=False`：

```python
registry.register_from_mcp("http://localhost:8000/mcp", persistent=False)
```

## 将 MCP 与 OpenAI 客户端集成

通过在 ToolRegistry 中注册 MCP 工具，可以增强 OpenAI 工作流，为聊天补全提供工具模式以实现自动化执行。

### 设置 OpenAI 客户端和 MCP 工具注册

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
    model="deepseek-chat", messages=messages, tools=registry.get_schemas(), tool_choice="auto"
)
```

### 执行工具调用并回传结果

如果模型决定使用 MCP 工具，提取 `tool_calls` 并自动执行：

```python
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls

    # Execute tool calls
    tool_responses = registry.execute_tool_calls(tool_calls)

    # Construct assistant messages and extend conversation
    assistant_tool_messages = registry.build_tool_call_messages(tool_calls, tool_responses)
    messages.extend(assistant_tool_messages)

    # Feed updated messages back to the model
    second_response = client.chat.completions.create(
        model="deepseek-chat", messages=messages
    )

    print(second_response.choices[0].message.content)
```

### 最终输出

LLM 将处理 MCP 工具返回的结果并相应地做出回复，完成查询。
