import json
import asyncio

from toolregistry import ToolRegistry

registry = ToolRegistry()


@registry.register
async def add(a: float, b: float) -> float:
    """Add two numbers together."""
    await asyncio.sleep(0.1)  # Simulate async operation
    return a + b


@registry.register
async def subtract(a: int, b: int) -> int:
    """Subtract the second number from the first."""
    await asyncio.sleep(0.1)  # Simulate async operation
    return a - b


async def main():
    print(registry.get_available_tools())

    add_func = registry.get_callable("add")
    print(type(add_func))
    value = await add_func(1, 2)
    print(value)

    add_func2 = registry["add"]
    print(type(add_func2))
    value = await add_func2(4, 5)
    print(value)

    add_tool = registry.get_tool("add")
    print(add_tool.parameters)
    print(type(add_tool))
    value = await add_tool.run({"a": 7, "b": 8})
    print(value)

    tools_json = registry.get_tools_json()
    print(json.dumps(tools_json, indent=2))

    print(json.dumps(add_tool.describe(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
