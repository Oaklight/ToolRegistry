import asyncio
import os

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

PORT = os.getenv("PORT", "8000")


async def sqlite_client():
    # 配置SSE服务器地址 (使用sqlite_server_sse.py)
    url = f"http://localhost:{PORT}/mcp/sse"  # 与sqlite_server_sse.py配置一致

    try:
        print(f"Connecting to SQLite SSE server at {url}")

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

                # 4. 调用SQLite工具
                if tools:
                    sqlite_tool = next(
                        (tool for tool in tools if tool.name == "sqlite_tool"), None
                    )
                    if sqlite_tool:
                        # 创建表
                        print("\nCreating test table:")
                        create_result = await session.call_tool(
                            sqlite_tool.name,
                            {
                                "operation": "execute",
                                "sql": "CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, name TEXT)",
                            },
                        )
                        print(f"Table created: {create_result}")

                        # 插入数据
                        print("\nInserting test data:")
                        insert_result = await session.call_tool(
                            sqlite_tool.name,
                            {
                                "operation": "execute",
                                "sql": "INSERT INTO test (name) VALUES (?)",
                                "parameters": ["Alice"],
                            },
                        )
                        print(f"Data inserted: {insert_result}")

                        # 查询数据
                        print("\nQuerying test data:")
                        query_result = await session.call_tool(
                            sqlite_tool.name,
                            {"operation": "query", "sql": "SELECT * FROM test"},
                        )
                        print("Query results:")
                        for row in query_result:
                            print(f"- ID: {row[0]}, Name: {row[1]}")

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
    asyncio.run(sqlite_client())
