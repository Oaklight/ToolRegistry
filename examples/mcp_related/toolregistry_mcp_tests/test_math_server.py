import asyncio
import os
from pprint import pprint

from toolregistry.tool_registry import ToolRegistry

PORT = os.getenv("PORT", 8002)  # 默认端口8002，可通过环境变量覆盖

registry = ToolRegistry()

mcp_server_url = f"http://localhost:{PORT}/mcp/sse"

registry.register_mcp_tools(mcp_server_url)
print("Registered Math Tools:")
pprint(registry)


def test_add():
    try:
        print("Testing add...")
        result = registry["add"](a=5, b=3)
        print(f"Add result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_subtract():
    try:
        print("Testing subtract...")
        result = registry["subtract"](a=10, b=4)
        print(f"Subtract result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_multiply():
    try:
        print("Testing multiply...")
        result = registry["multiply"](a=7, b=6)
        print(f"Multiply result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_divide():
    try:
        print("Testing divide...")
        result = registry["divide"](a=15, b=3)
        print(f"Divide result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


if __name__ == "__main__":
    test_add()
    test_subtract()
    test_multiply()
    test_divide()
