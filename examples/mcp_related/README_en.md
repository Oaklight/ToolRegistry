# MCP SSE Mode Usage Guide

[中文版](README_zh.md)

## Server Implementation

1. Create SSE server using FastMCP:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Server Name",
             sse_path="/sse",
             message_path="/mcp/messages/")
```

2. Register tools and resources (echo tool example):

```python
from mcp.server.models import Tool

@mcp.tool()
def echo_tool(message: str) -> str:
    """Echo a message as a tool"""
    return f"Tool echo: {message}"
```

3. Create and run Starlette application (FastMCP is essentially a Starlette app wrapper):

```python
app = mcp.sse_app()
```

**Assuming you're in the examples directory**
Run server:

```bash
uvicorn mcp_related.mcp_servers.echo_server_sse:app --port 8001
```

Other server examples:

```bash
uvicorn mcp_related.mcp_servers.math_server_sse:app --port 8002
uvicorn mcp_related.mcp_servers.sqlite_server_sse:app --port 8003
uvicorn mcp_related.mcp_servers.str_ops_client_sse:app --port 8004
uvicorn mcp_related.mcp_servers.everything_server_sse:app --port 8005
```

## Client Implementation

Run client:

```bash
PORT=8001 python examples/mcp_clients/echo_client_sse.py
```

Other client examples:

```bash
PORT=8002 python examples/mcp_clients/math_client_sse.py
PORT=8003 python examples/mcp_clients/sqlite_client_sse.py
```

1. Create SSE client connection:

```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async with sse_client("http://localhost:8001/sse") as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
```

2. Get tools list:

```python
tools_response = await session.list_tools()
tools = tools_response.tools  # Note: directly access .tools property
for tool in tools:
    print(f"- {tool.name}: {tool.description}")
```

3. Call tool:

```python
result = await session.call_tool(
    "echo_tool",
    {"message": "Hello from client!"}
)
print(f"Tool result: {result}")
```

## Common Issues

1. **Framework Choice**:

   - Simplified SSE server creation through FastMCP (essentially a Starlette app wrapper)

2. **Tools List Processing Error**:

   - Error: AttributeError: 'ListToolsResult' object has no attribute 'get'
   - Solution: Use .tools property directly instead of .get() method

3. **Variable Scope Issue**:

   - Ensure result variable is defined and used in correct scope

4. **Tool Calling Format**:

   - Tool name must match registration
   - Input parameters must conform to defined schema

5. **Connection Issues**:
   - Ensure server is running and listening on correct port
   - Verify URL path is correct (typically /sse)

## Example Code

Available server and client pairs:

| Server File                                                                           | Client File                                                                           | Description                |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | -------------------------- |
| [echo_server_sse.py](examples/mcp_related/mcp_servers/echo_server_sse.py)             | [echo_client_sse.py](examples/mcp_related/mcp_clients/echo_client_sse.py)             | Echo test                  |
| [everything_server_sse.py](examples/mcp_related/mcp_servers/everything_server_sse.py) | [everything_client_sse.py](examples/mcp_related/mcp_clients/everything_client_sse.py) | Full feature test          |
| [math_server_sse.py](examples/mcp_related/mcp_servers/math_server_sse.py)             | [math_client_sse.py](examples/mcp_related/mcp_clients/math_client_sse.py)             | Math operations            |
| [sqlite_server_sse.py](examples/mcp_related/mcp_servers/sqlite_server_sse.py)         | [sqlite_client_sse.py](examples/mcp_related/mcp_clients/sqlite_client_sse.py)         | SQLite database operations |
| [str_ops_server_sse.py](examples/mcp_related/mcp_servers/str_ops_server_sse.py)       | [str_ops_client_sse.py](examples/mcp_related/mcp_clients/str_ops_client_sse.py)       | String operations          |

All files located at:

- Server examples: examples/mcp_servers/
- Client examples: examples/mcp_clients/
