import asyncio
import os
from pprint import pprint

from toolregistry.tool_registry import ToolRegistry

PORT = os.getenv("PORT", 8004)  # 默认端口8004，可通过环境变量覆盖

registry = ToolRegistry()

mcp_server_url = f"http://localhost:{PORT}/mcp/sse"

registry.register_from_mcp(mcp_server_url)
print("Registered String Operations Tools:")
pprint(registry)


def test_reverse_string():
    try:
        print("Testing reverse_string...")
        result = registry["reverse_string"]("hello")
        print(f"Reverse result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_count_words():
    try:
        print("Testing count_words...")
        result = registry["count_words"]("This is a test sentence")
        print(f"Word count: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_uppercase():
    try:
        print("Testing uppercase...")
        result = registry["uppercase"]("hello")
        print(f"Uppercase result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_lowercase():
    try:
        print("Testing lowercase...")
        result = registry["lowercase"]("HELLO")
        print(f"Lowercase result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


if __name__ == "__main__":
    test_reverse_string()
    test_count_words()
    test_uppercase()
    test_lowercase()
