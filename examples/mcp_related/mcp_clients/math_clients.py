"""Client examples using the `fastmcp` library.

This module demonstrates client-side usage of the fastmcp library
for math operations with MCP servers.
"""

import asyncio
import os

from fastmcp import Client

from ..mcp_servers.math_server import mcp

PORT = os.getenv("PORT", "8000")


async def test_math_client(client: Client):
    """测试数学工具的统一函数"""
    try:
        async with client:
            print(f"\nTesting to server with transport: {client.transport}")

            print("\nGetting available tools:")
            tools = await client.list_tools()
            for tool in tools:
                print(f"- {tool.name}: {tool.description}")

            # 加法示例
            print("\nCalling 'add' - Addition:")
            add_result = await client.call_tool("add", {"a": 10, "b": 5})
            print(f"10 + 5 = {add_result}")

            # 减法示例
            print("\nCalling 'subtract' - Subtraction:")
            sub_result = await client.call_tool("subtract", {"a": 10, "b": 5})
            print(f"10 - 5 = {sub_result}")

            # 乘法示例
            print("\nCalling 'multiply' - Multiplication:")
            mul_result = await client.call_tool("multiply", {"a": 10, "b": 5})
            print(f"10 * 5 = {mul_result}")

            # 除法示例
            print("\nCalling 'divide' - Division:")
            div_result = await client.call_tool("divide", {"a": 10, "b": 5})
            print(f"10 / 5 = {div_result}")
            print("\nGetting available resources:")

            resources = await client.list_resources()
            for each in resources:
                print(each)

    except Exception as e:
        print("\nError details:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        if hasattr(e, "__traceback__"):
            import traceback

            traceback.print_exc()


async def main():
    """测试所有类型的math_server"""
    # 1. stdio服务器
    stdio_server = mcp
    client_stdio = Client(stdio_server)

    # 2. SSE服务器
    sse_url = f"http://localhost:{PORT}/sse"
    client_sse = Client(sse_url)

    # 测试所有客户端
    await test_math_client(client_stdio)
    await test_math_client(client_sse)


if __name__ == "__main__":
    asyncio.run(main())
