import asyncio
import os
from pprint import pprint

from toolregistry.tool_registry import ToolRegistry

PORT = os.getenv("PORT", 8000)  # 默认端口8000，可通过环境变量覆盖

registry = ToolRegistry()

mcp_server_url = f"http://localhost:{PORT}/mcp/sse"

registry.register_mcp_tools(mcp_server_url)
print("Registered Tools:")
pprint(registry)


def test_echo_sync():
    try:
        print("Testing echo sync call...")
        result = registry["echo"]("test echo sync call")
        print(f"Echo sync result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_add_sync():
    try:
        print("Testing add sync call...")
        result = registry["add"](a=5, b=3)
        print(f"Add sync result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


async def test_long_running_async():
    try:
        print("Testing long_running async call...")
        result = await registry["long_running"].__acall__(duration=2, steps=4)
        print(f"Long running async result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


async def test_sample_llm_async():
    try:
        print("Testing sample_llm async call...")
        result = await registry["sample_llm"].__acall__(
            prompt="What is the meaning of life?", max_tokens=50
        )
        print(f"Sample LLM async result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


async def test_annotated_message_async():
    try:
        print("Testing annotated_message async call...")
        result = await registry["annotated_message"].__acall__(
            message_type="success", include_image=True
        )
        print(f"Annotated message async result: {result}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


if __name__ == "__main__":
    test_echo_sync()
    test_add_sync()
    asyncio.run(test_long_running_async())
    asyncio.run(test_sample_llm_async())
    asyncio.run(test_annotated_message_async())
