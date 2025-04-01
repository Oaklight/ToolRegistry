import json

from toolregistry import ToolRegistry

registry = ToolRegistry()


@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@registry.register
def subtract(a: int, b: int) -> int:
    """Subtract the second number from the first."""
    return a - b


print(registry.get_available_tools())

add_func = registry.get_callable("add")
print(type(add_func))
value = add_func(1, 2)
print(value)

add_func2 = registry["add"]
print(type(add_func2))
value = add_func2(4, 5)
print(value)


add_tool = registry.get_tool("add")
print(add_tool.parameters)
print(type(add_tool))
value = add_tool.run({"a": 7, "b": 8})
print(value)

tools_json = registry.get_tools_json()

print(json.dumps(tools_json, indent=2))
