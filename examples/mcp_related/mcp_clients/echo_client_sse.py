import asyncio
import os

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

PORT = os.getenv("PORT", "8000")


async def echo_client():
    # 配置SSE服务器地址 (使用echo_server_sse.py)
    url = f"http://localhost:{PORT}/mcp/sse"  # 与echo_server_sse.py配置一致

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

                # 4. 调用echo工具
                if tools:
                    echo_tool = next(
                        (tool for tool in tools if tool.name == "echo_tool"), None
                    )
                    if echo_tool:
                        print(f"\nCalling tool: {echo_tool.name}")
                        result = await session.call_tool(
                            echo_tool.name, {"message": "Hello from Echo Client!"}
                        )
                        print(f"Tool result: {result}")

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
    asyncio.run(echo_client())
