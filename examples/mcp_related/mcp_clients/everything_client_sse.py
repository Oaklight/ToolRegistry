import asyncio
import os

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

PORT = os.getenv("PORT", "8000")


async def everything_client():
    # 配置SSE服务器地址 (使用everything_server_sse.py)
    url = f"http://localhost:{PORT}/sse"  # 与everything_server_sse.py配置一致

    try:
        print(f"Connecting to SSE server at {url}")

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

                # 4. 调用多个工具示例
                if tools:
                    # 调用echo工具
                    echo_tool = next(
                        (tool for tool in tools if tool.name == "echo_tool"), None
                    )
                    if echo_tool:
                        print(f"\nCalling tool: {echo_tool.name}")
                        result = await session.call_tool(
                            echo_tool.name, {"message": "Hello from Everything Client!"}
                        )
                        print(f"Echo result: {result}")

                    # 调用math工具
                    math_tool = next(
                        (tool for tool in tools if tool.name == "math_tool"), None
                    )
                    if math_tool:
                        print(f"\nCalling tool: {math_tool.name}")
                        result = await session.call_tool(
                            math_tool.name, {"operation": "add", "a": 5, "b": 3}
                        )
                        print(f"Math result: {result}")

                    # 调用string工具
                    str_tool = next(
                        (tool for tool in tools if tool.name == "string_ops_tool"), None
                    )
                    if str_tool:
                        print(f"\nCalling tool: {str_tool.name}")
                        result = await session.call_tool(
                            str_tool.name, {"operation": "reverse", "text": "hello"}
                        )
                        print(f"String result: {result}")

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
    asyncio.run(everything_client())
