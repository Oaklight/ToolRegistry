import asyncio
import os
from pprint import pprint

from toolregistry import ToolRegistry

PORT = os.getenv("PORT", 8000)  # default port 8000, change via environment variable

registry = ToolRegistry()

mcp_server_url = f"http://localhost:{PORT}/mcp/sse"

# sync register
registry.register_mcp_tools(mcp_server_url)
# pprint(registry)


# async register
async def async_register():
    await registry.register_mcp_tools_async(mcp_server_url)
    pprint(registry)


asyncio.run(async_register())


# accessing the mcp tools as callable via __getitem__ (might be some other proper name for this method)
add_func = registry["add"]
result = add_func(1, 2)
print(result)

# accessing the mcp tools as callable via get_callable
add_func = registry.get_callable("add")
result = add_func(3, 4)
print(result)

# accessing the mcp tools as toolregistry.tool.Tool
add_tool = registry.get_tool("add")
result = add_tool.run({"a": 5, "b": 6})
print(result)


# async access:
async def call_async_add_func():
    add_func = registry.get_callable("add")
    result = await add_func(7, 7)
    print(result)

    add_func2 = registry["add"]
    result = await add_func2(7, 8)
    print(result)


asyncio.run(call_async_add_func())


async def call_async_add_tool():
    add_tool = registry.get_tool("add")
    result = await add_tool.arun({"a": 9, "b": 10})
    print(result)


asyncio.run(call_async_add_tool())
