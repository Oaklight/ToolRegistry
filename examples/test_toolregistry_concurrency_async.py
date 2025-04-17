import asyncio
import json
import string
import time
from pprint import pprint
from typing import Any, Dict, List

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

from toolregistry import ToolRegistry


def generate_tool_calls(n: int, callable_name: str = "add") -> List[Dict[str, Any]]:
    import random

    return [
        ChatCompletionMessageToolCall(
            id="id_" + "".join(random.sample(string.hexdigits, 4)),
            function=Function(
                arguments=json.dumps(
                    {
                        "a": random.randint(1, 100),
                        "b": random.randint(1, 100),
                    }
                ),
                name=callable_name,
            ),
            type="function",
        )
        for _ in range(n)
    ]


class AsyncCalculator:
    async def add(self, a: int, b: int) -> int:
        await asyncio.sleep(0)  # simulate async operation
        return a + b

    async def subtract(self, a: int, b: int) -> int:
        await asyncio.sleep(0)
        return a - b

    async def multiply(self, a: int, b: int) -> int:
        await asyncio.sleep(0)
        return a * b

    async def divide(self, a: int, b: int) -> float:
        await asyncio.sleep(0)
        if b == 0:
            raise ValueError("Division by zero")
        return a / b


async def main():
    # ========= async hub tools =========

    N = 10
    registry = ToolRegistry()
    registry.register_from_class(AsyncCalculator)
    print(registry.get_available_tools())
    tool_calls = generate_tool_calls(N)

    start_time = time.time()
    results = registry.execute_tool_calls(tool_calls)
    elapsed = time.time() - start_time

    assert len(results) == N

    pprint(results)

    print(f"Executed {N} async tool calls in {elapsed:.4f} seconds")
    print(f"Throughput: {N/elapsed:.2f} calls/second")


if __name__ == "__main__":
    asyncio.run(main())
