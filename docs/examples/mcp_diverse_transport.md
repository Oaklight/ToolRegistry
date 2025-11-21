# Register MCP Tools via Diverse Transports

MCP protocol supports a variety of transports for communication. Below are examples of how to register tools using different types of transports.

```python
from pathlib import Path
from pprint import pprint

from fastmcp import FastMCP
from fastmcp.client.transports import StreamableHttpTransport

from toolregistry.tool_registry import ToolRegistry

registry = ToolRegistry()

transport = "https://mcphub.example.com/mcp"  # mcp streamable http
transport = "http://localhost:8000/sse/test_group"  # mcp http+sse
transport = (
    "examples/mcp_related/mcp_servers/math_server.py"  # Path to mcp server script
)
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
}  # Example mcp configuration dict
transport = FastMCP(name="MyFastMCP")  # naive FastMCP instance
transport = StreamableHttpTransport(
    url="https://mcphub.example.com/mcp", headers={"Authorization": "Bearer token"}
)  # Transport instance, useful if you have custom headers

registry.register_from_mcp(transport)
print("Registered Tools:")
pprint(registry)
```
