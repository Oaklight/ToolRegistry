"""Client test file using `mcp` package directly.

This module demonstrates client-side usage of the MCP protocol by directly
interacting with the `mcp` package for math operations.
"""

import asyncio
import os

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

PORT = os.getenv("PORT", "8000")


async def math_client():
    # 配置SSE服务器地址 (使用math_server_sse.py)
    url = f"http://localhost:{PORT}/mcp/sse"  # 与math_server_sse.py配置一致

    try:
        print(f"Connecting to Math SSE server at {url}")

        # 1. 创建SSE连接
        async with sse_client(url) as (read_stream, write_stream):
            # 2. 创建客户端会话
            async with ClientSession(read_stream, write_stream) as session:
                print("Connected to server, initializing session...")
                await session.initialize()

                # 3. 获取工具列表
                print("\nGetting available tools:")
                tools_response = await session.list_tools()
                tools = tools_response.tools
                for tool in tools:
                    print(f"- {tool.name}: {tool.description}")

                # 4. 调用数学工具
                if tools:
                    math_tool = next(
                        (tool for tool in tools if tool.name == "math_tool"), None
                    )
                    if math_tool:
                        # 加法示例
                        print(f"\nCalling {math_tool.name} - Addition:")
                        add_result = await session.call_tool(
                            math_tool.name, {"operation": "add", "a": 10, "b": 5}
                        )
                        print(f"10 + 5 = {add_result}")

                        # 减法示例
                        print(f"\nCalling {math_tool.name} - Subtraction:")
                        sub_result = await session.call_tool(
                            math_tool.name, {"operation": "subtract", "a": 10, "b": 5}
                        )
                        print(f"10 - 5 = {sub_result}")

                        # 乘法示例
                        print(f"\nCalling {math_tool.name} - Multiplication:")
                        mul_result = await session.call_tool(
                            math_tool.name, {"operation": "multiply", "a": 10, "b": 5}
                        )
                        print(f"10 * 5 = {mul_result}")

                        # 除法示例
                        print(f"\nCalling {math_tool.name} - Division:")
                        div_result = await session.call_tool(
                            math_tool.name, {"operation": "divide", "a": 10, "b": 5}
                        )
                        print(f"10 / 5 = {div_result}")

                # 5. 获取资源列表
                print("\nGetting available resources:")
                resources = await session.list_resources()
                for uri, desc in resources:
                    print(f"- {uri}: {desc}")

    except Exception as e:
        print(f"\nError details:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        if hasattr(e, "__traceback__"):
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(math_client())
