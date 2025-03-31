import asyncio
import os
from pprint import pprint

from toolregistry.tool_registry import ToolRegistry

PORT = os.getenv("PORT", 8000)

registry = ToolRegistry()

mcp_server_url = f"http://localhost:{PORT}/mcp/sse"

registry.register_mcp_tools(mcp_server_url)
print("Tools JSON:")
pprint(registry)

# echo_tool = registry._tools["echo_tool"]
# print(echo_tool.run(**{"message": "a very simple echo test"}))

# result = registry["echo_tool"]("try a simple echo")
# print(result)


def test():
    try:
        # test sync method, directly call as callable
        print("Testing sync call...")
        result = registry["echo_tool"]("test sync call")
        print(f"Sync call result: {result}")

        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


test()


def test2():
    try:
        # test sync method, call it as Tool
        print("Testing sync call...")
        echo_tool = registry._tools["echo_tool"]
        result = echo_tool.run("test sync call")
        print(f"Sync call result: {result}")

        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


test2()


async def atest():
    try:
        # test async method, directly call as callable
        print("Testing async call...")
        result = await registry["echo_tool"].__acall__("test async call")
        print(f"Async call result: {result}")

        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


# 运行异步测试
asyncio.run(atest())


async def atest2():
    try:
        # test async method, call it as Tool
        print("Testing async call...")
        echo_tool = registry._tools["echo_tool"]
        result = await echo_tool.arun("test async call")
        print(f"Async call result: {result}")

        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


# 运行异步测试
asyncio.run(atest2())
