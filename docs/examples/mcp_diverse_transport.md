# Register MCP Tools via Diverse Transports

MCP protocol supports a variety of transports for communication. Below are examples of how to register tools using different types of transports.

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
