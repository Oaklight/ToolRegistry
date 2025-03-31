import asyncio
import os
from pprint import pprint

from toolregistry.tool_registry import ToolRegistry

PORT = os.getenv("PORT", 8000)  # 默认端口8000，可通过环境变量覆盖

registry = ToolRegistry()

mcp_server_url = f"http://localhost:{PORT}/mcp/sse"

registry.register_mcp_tools(mcp_server_url)
print("Registered Tools:")
pprint(registry)


def test_sync_call():
    try:
        print("Testing echo sync call...")
        result = registry["echo_tool"]("test echo sync call")
        print(f"Sync call result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_sync_tool():
    try:
        print("Testing echo sync tool...")
        echo_tool = registry._tools["echo_tool"]
        result = echo_tool.run("test echo sync tool")
        print(f"Sync tool result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


async def test_async_call():
    try:
        print("Testing echo async call...")
        result = await registry["echo_tool"].__acall__("test echo async call")
        print(f"Async call result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


async def test_async_tool():
    try:
        print("Testing echo async tool...")
        echo_tool = registry._tools["echo_tool"]
        result = await echo_tool.arun("test echo async tool")
        print(f"Async tool result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


if __name__ == "__main__":
    test_sync_call()
    test_sync_tool()
    asyncio.run(test_async_call())
    asyncio.run(test_async_tool())
