# MCP SSE 模式使用指南

## 服务器端实现

1. 使用 FastMCP 创建 SSE 服务器：

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Server Name",
             sse_path="/mcp/sse",
             message_path="/mcp/messages/")
```

2. 注册工具和资源（以 echo 工具为例）：

```python
from mcp.server.models import Tool

@mcp.tool()
def echo_tool(message: str) -> str:
    """Echo a message as a tool"""
    return f"Tool echo: {message}"
```

3. 创建并运行 Starlette 应用（FastMCP 默认即为一个 Starlette 应用）：

```python
app = mcp.sse_app()
```

**假设你位于 examples 目录下**
运行服务器：

```bash
uvicorn mcp_related.mcp_servers.echo_server_sse:app --port 8001
```

其他服务器示例：

```bash
uvicorn mcp_related.mcp_servers.math_server_sse:app --port 8002
uvicorn mcp_related.mcp_servers.sqlite_server_sse:app --port 8003
uvicorn mcp_related.mcp_servers.str_ops_client_sse:app --port 8004
uvicorn mcp_related.mcp_servers.everything_server_sse:app --port 8005
```

## 客户端实现

运行客户端：

```bash
PORT=8001 python examples/mcp_clients/echo_client_sse.py
```

其他客户端示例：

```bash
PORT=8002 python examples/mcp_clients/math_client_sse.py
PORT=8003 python examples/mcp_clients/sqlite_client_sse.py
```

1. 创建 SSE 客户端连接：

```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async with sse_client("http://localhost:8001/mcp/sse") as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
```

2. 获取工具列表：

```python
tools_response = await session.list_tools()
tools = tools_response.tools  # 注意这里是直接访问.tools属性
for tool in tools:
    print(f"- {tool.name}: {tool.description}")
```

3. 调用工具：

```python
result = await session.call_tool(
    "echo_tool",
    {"message": "Hello from client!"}
)
print(f"Tool result: {result}")
```

## 常见问题

1. **框架选择**：

   - 通过 FastMCP 简化 SSE 服务器创建。其本质是一个Starlette的应用封装。
   <!-- - 服务器使用 Starlette 而非 FastAPI -->

2. **工具列表处理错误**：

   - 错误：AttributeError: 'ListToolsResult' object has no attribute 'get'
   - 解决：直接使用.tools 属性而非.get()方法

3. **变量作用域问题**：

   - 确保 result 变量在正确的作用域内定义和使用

4. **工具调用格式**：

   - 工具名称需与注册时一致
   - 输入参数需符合定义的 schema

5. **连接问题**：
   - 确保服务器已启动并监听正确端口
   - 检查 URL 路径是否正确（通常为/mcp/sse）

## 示例代码

以下是可用的服务器和客户端对应表：

| 服务器文件                                                                            | 客户端文件                                                                            | 功能描述          |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------------- |
| [echo_server_sse.py](examples/mcp_related/mcp_servers/echo_server_sse.py)             | [echo_client_sse.py](examples/mcp_related/mcp_clients/echo_client_sse.py)             | 回声测试          |
| [everything_server_sse.py](examples/mcp_related/mcp_servers/everything_server_sse.py) | [everything_client_sse.py](examples/mcp_related/mcp_clients/everything_client_sse.py) | 完整功能测试      |
| [math_server_sse.py](examples/mcp_related/mcp_servers/math_server_sse.py)             | [math_client_sse.py](examples/mcp_related/mcp_clients/math_client_sse.py)             | 数学运算          |
| [sqlite_server_sse.py](examples/mcp_related/mcp_servers/sqlite_server_sse.py)         | [sqlite_client_sse.py](examples/mcp_related/mcp_clients/sqlite_client_sse.py)         | SQLite 数据库操作 |
| [str_ops_server_sse.py](examples/mcp_related/mcp_servers/str_ops_server_sse.py)       | [str_ops_client_sse.py](examples/mcp_related/mcp_clients/str_ops_client_sse.py)       | 字符串操作        |

所有文件位于：

- 服务器示例: examples/mcp_servers/
- 客户端示例: examples/mcp_clients/
