# 通过多种传输方式注册 MCP 工具

MCP 协议支持多种通信传输方式。以下示例展示了如何使用不同类型的传输方式注册工具。

```python
from pathlib import Path
from pprint import pprint

from toolregistry import ToolRegistry

registry = ToolRegistry()

# Streamable HTTP transport
transport = "https://mcphub.example.com/mcp"

# SSE transport (legacy, path ends with /sse)
transport = "http://localhost:8000/sse/test_group"

# WebSocket transport
transport = "ws://localhost:8000/mcp"

# Stdio transport via script path
transport = "examples/mcp_related/mcp_servers/math_server.py"

# Stdio transport via dict config
transport = {
    "command": "python",
    "args": [
        "examples/mcp_related/mcp_servers/math_server.py"
    ],
    "env": {},
}

registry.register_from_mcp(transport)
print("Registered Tools:")
pprint(registry)
```
