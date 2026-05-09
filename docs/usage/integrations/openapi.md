# OpenAPI 工具使用指南

???+ note "变更日志"
    - API 更新于版本：0.4.12
    - 新增于版本：0.4.0

## 简介

本指南介绍如何将 OpenAPI 与 ToolRegistry 集成，使你能够基于 OpenAPI 规范注册和调用工具。指南以数学服务为例，提供了同步和异步注册方法的示例。

## 版本 0.4.12 中的 API 变更

`register_from_openapi` 方法现在接受两个参数：

- `client_config`：一个 `toolregistry.integrations.openapi.HttpClientConfig` 对象，用于配置与 API 交互的 HTTP 客户端。你可以配置请求头、授权方式、超时时间和其他设置，比之前的版本提供了更大的灵活性。
- `openapi_spec`：OpenAPI 规范，类型为 `Dict[str, Any]`，通过 `load_openapi_spec` 或 `load_openapi_spec_async` 等函数加载。这些函数接受 OpenAPI 规范的文件路径、URL 或基础 API 的 URL，并返回解析后的 OpenAPI 规范字典。

你现在必须显式传递 `client_config` 和 `openapi_spec` 这两个参数。

## OpenAPI 工具注册

### 同步注册

你可以使用 `register_from_openapi` 方法同步注册 OpenAPI 工具。例如：

```python
import os
from toolregistry.integrations.openapi import HttpClientConfig, load_openapi_spec
from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)  # Default port is 8000; can be overridden by an environment variable
registry = ToolRegistry()
client_config = HttpClientConfig(base_url=f"http://localhost:{PORT}")
openapi_spec = load_openapi_spec("http://localhost:{PORT}")  # Auto-discovery of OpenAPI spec

# Synchronously register OpenAPI tools
registry.register_from_openapi(client_config=client_config, openapi_spec=openapi_spec)
print(registry)  # Output: A ToolRegistry object with the registered OpenAPI tools
```

你应该会看到如下输出的模式信息。这里为了简洁，只展示第一个条目。

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

### 异步注册

在异步环境中，使用 `register_from_openapi_async` 方法注册工具：

```python
import asyncio
import os
from toolregistry.integrations.openapi import HttpClientConfig, load_openapi_spec_async
from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)
registry = ToolRegistry()
client_config = HttpClientConfig(base_url=f"http://localhost:{PORT}")

async def async_register():
    openapi_spec = await load_openapi_spec_async("http://localhost:{PORT}")  # Auto-discovery of OpenAPI spec
    await registry.register_from_openapi_async(client_config=client_config, openapi_spec=openapi_spec)
    print(registry)  # Optionally, inspect the registry for registered tools

asyncio.run(async_register())
```

### HTTP 客户端配置

在某些情况下，OpenAPI 服务可能需要特定的配置，例如自定义请求头、超时时间或 SSL 证书。你可以通过 `HttpClientConfig` 类来调整这些设置。以下是在请求头中使用 Bearer Token 授权的示例。

```python
from toolregistry.integrations.openapi import HttpClientConfig

OPENAPI_SERVER_URL = os.getenv("OPENAPI_SERVER_URL", "http://localhost:8000")
OPENAPI_BEARER_TOKENS = os.getenv("OPENAPI_BEARER_TOKENS", "your-api-token")

client_config = HttpClientConfig(
    base_url=OPENAPI_SERVER_URL,
    headers={"Authorization": f"Bearer {OPENAPI_BEARER_TOKENS}"}, # this sets the Bearer token
)
```

如果不需要特殊配置，只需使用 `base_url` 创建 HttpClientConfig 即可：

```python
from toolregistry.integrations.openapi import HttpClientConfig

client_config = HttpClientConfig(
    base_url=OPENAPI_SERVER_URL,
)
```

### 加载 OpenAPI 规范

使用 `load_openapi_spec` 或 `load_openapi_spec_async` 函数时，适用以下行为：

1. **提供基础 URL**：如果你只指定一个基础 URL（例如 `http://localhost:8000`），加载器将尝试"尽力"自动发现 OpenAPI 规范文件。它会检查诸如 `http://<base_url>/openapi.json`、`http://<base_url>/swagger.json` 等端点。如果自动发现失败，请确保基础 URL 正确且规范文件可访问。
2. **提供文件路径**：如果你提供文件路径（例如 `./openapi_spec.json`），函数将直接从文件加载 OpenAPI 规范。与简单的直接加载不同，该功能包括展开 OpenAPI 规范中常见的 `$ref` 块。这确保了返回的字典中所有模式引用都已完全解析。

```python
from toolregistry.integrations.openapi import load_openapi_spec

openapi_spec = load_openapi_spec("./openapi_spec.json") # Load from file
openapi_spec = load_openapi_spec("http://localhost:8000") # auto-discovery with URL to service root
openapi_spec = load_openapi_spec("http://localhost:8000/openapi.json") # load from specification URL
```

## 持久连接

???+ note "变更日志"
    新增于版本：0.7.0

默认情况下，OpenAPI 集成现在使用**持久 HTTP 连接**——HTTP 客户端在多次工具调用之间被复用，从而实现连接池化并降低延迟。

### 上下文管理器用法

使用 `ToolRegistry` 作为上下文管理器可确保 HTTP 客户端被正确关闭：

```python
from toolregistry import ToolRegistry
from toolregistry.integrations.openapi import HttpClientConfig, load_openapi_spec

with ToolRegistry() as registry:
    client_config = HttpClientConfig(base_url="http://localhost:8000")
    openapi_spec = load_openapi_spec("http://localhost:8000")
    registry.register_from_openapi(client_config=client_config, openapi_spec=openapi_spec)
    result = registry["add_get"](1, 2)
# HTTP clients are automatically closed on exit
```
```

### 显式清理

```python
registry = ToolRegistry()
registry.register_from_openapi(client_config=client_config, openapi_spec=openapi_spec)
# ... use tools ...
registry.close()  # Close all persistent HTTP clients

# Or in async code:
await registry.close_async()
```

### 退出持久连接模式

要每次调用时创建新的 HTTP 客户端（旧行为），请传递 `persistent=False`：

```python
registry.register_from_openapi(
    client_config=client_config, openapi_spec=openapi_spec, persistent=False
)
```

## 调用 OpenAPI 工具

OpenAPI 工具注册完成后，支持同步和异步两种调用方式。

### 同步调用

工具可以作为 Python 可调用对象直接调用，也可以通过 `get_callable` 或 `get_tool` 方法获取后调用：

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

### 异步调用

对于异步调用，可以使用可调用对象的 `__call__` 方法或工具对象的 `arun` 方法：

```python
import asyncio

async def call_async_add_func():
    # Direct subscript access for asynchronous invocation
    add_func = registry["add_get"]
    result = await add_func(7, 7)
    print(result)  # Expected output: 14.0

asyncio.run(call_async_add_func())

async def call_async_add_tool():
    # Retrieve the tool object for asynchronous invocation
    add_tool = registry.get_tool("add_get")
    result = await add_tool.arun({"a": 9, "b": 10})
    print(result)  # Expected output: 19.0

asyncio.run(call_async_add_tool())
```

## 将 OpenAPI 与 OpenAI 客户端集成

你可以将 OpenAPI 工具注册集成到 OpenAI 兼容的 API 工作流中。以下更新后的示例使用了新的 API：

```python
from dotenv import load_dotenv
from toolregistry.integrations.openapi import HttpClientConfig, load_openapi_spec
from toolregistry import ToolRegistry
from openai import OpenAI
import os

# Load environment variables from .env file
load_dotenv()
PORT = os.getenv("PORT", 8000)  # default port 8000, change via environment variable

registry = ToolRegistry()
client_config = HttpClientConfig(base_url=f"http://localhost:{PORT}")
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
    tools=registry.get_schemas(),
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
    assistant_tool_messages = registry.build_tool_call_messages(
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

## 注意事项

1. OpenAPI 工具注册支持同步和异步两种方法。工具注册完成后，可以作为简单的 Python 函数或工具对象进行调用。
2. 调用时，参数会根据工具定义自动转换。例如，`add_get` 工具期望数值输入并返回数值结果。
3. 与 OpenAI 客户端的集成使你能够将工具执行无缝整合到聊天工作流中。

按照上述示例即可高效地将 OpenAPI 工具与 ToolRegistry 集成并使用。
