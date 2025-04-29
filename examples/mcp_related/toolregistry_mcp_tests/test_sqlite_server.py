import asyncio
import os
import sqlite3
from pprint import pprint

from toolregistry.tool_registry import ToolRegistry

# 准备测试数据库
conn = sqlite3.connect("test.db")
conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
conn.execute("INSERT OR IGNORE INTO users (id, name) VALUES (1, 'Alice')")
conn.execute("INSERT OR IGNORE INTO users (id, name) VALUES (2, 'Bob')")
conn.commit()
conn.close()

PORT = os.getenv("PORT", 8003)  # 默认端口8003，可通过环境变量覆盖

registry = ToolRegistry()

mcp_server_url = f"http://localhost:{PORT}/sse"

registry.register_from_mcp(mcp_server_url)
print("Registered SQLite Tools:")
pprint(registry)


def test_get_schema():
    try:
        print("Testing get_schema...")
        result = registry["get_schema"]()
        print(f"Schema result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_query_data():
    try:
        print("Testing query_data...")
        result = registry["query_data"]("SELECT * FROM users")
        print(f"Query result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


if __name__ == "__main__":
    test_get_schema()
    test_query_data()
