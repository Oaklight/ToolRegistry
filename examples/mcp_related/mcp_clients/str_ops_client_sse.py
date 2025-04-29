import asyncio
import os

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

PORT = os.getenv("PORT", "8000")


async def str_ops_client():
    # 配置SSE服务器地址 (使用str_ops_server_sse.py)
    url = f"http://localhost:{PORT}/sse"  # 与str_ops_server_sse.py配置一致

    try:
        print(f"Connecting to String Operations SSE server at {url}")

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

                # 4. 调用字符串操作工具
                if tools:
                    str_tool = next(
                        (tool for tool in tools if tool.name == "string_ops_tool"), None
                    )
                    if str_tool:
                        # 反转字符串
                        print("\nReversing string:")
                        reverse_result = await session.call_tool(
                            str_tool.name,
                            {"operation": "reverse", "text": "Hello World"},
                        )
                        print(f"Reversed: {reverse_result}")

                        # 大写转换
                        print("\nConverting to uppercase:")
                        upper_result = await session.call_tool(
                            str_tool.name,
                            {"operation": "uppercase", "text": "Hello World"},
                        )
                        print(f"Uppercase: {upper_result}")

                        # 小写转换
                        print("\nConverting to lowercase:")
                        lower_result = await session.call_tool(
                            str_tool.name,
                            {"operation": "lowercase", "text": "Hello World"},
                        )
                        print(f"Lowercase: {lower_result}")

                        # 计算长度
                        print("\nCalculating length:")
                        length_result = await session.call_tool(
                            str_tool.name,
                            {"operation": "length", "text": "Hello World"},
                        )
                        print(f"Length: {length_result}")

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
    asyncio.run(str_ops_client())
