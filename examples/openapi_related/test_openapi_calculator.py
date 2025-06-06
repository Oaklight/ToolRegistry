import asyncio

from toolregistry.openapi import HttpxClientConfig, load_openapi_spec
from toolregistry.tool_registry import ToolRegistry

base_url = "http://localhost:8000"
openapi_spec = load_openapi_spec(base_url)

client_config = HttpxClientConfig(base_url=base_url)

# Initialize the ToolRegistry and register OpenAPI tools synchronously
registry = ToolRegistry()
registry.register_from_openapi(client_config, openapi_spec, with_namespace=True)

# print("Registry:", registry)

print(registry.get_available_tools())

# -------------------------------
# Synchronous Tests
# -------------------------------

# Direct access using subscript notation
add_func = registry["open_api_calculator-add_get"]
result = add_func(1, 2)
print(result)  # Expected output: 3.0

# Retrieve the callable with get_callable and call it
add_func = registry.get_callable("open_api_calculator-add_get")
result = add_func(3, 4)
print(result)  # Expected output: 7.0

# Retrieve the tool object with get_tool and invoke its run method
add_tool = registry.get_tool("open_api_calculator-add_get")
result = add_tool.run({"a": 5, "b": 6})
print(result)  # Expected output: 11.0

# -------------------------------
# Asynchronous Tests
# -------------------------------


async def call_async_add_func():
    # Retrieve the tool callable for asynchronous invocation
    add_func = registry.get_callable("open_api_calculator-add_get")
    result = await add_func(7, 7)
    print(result)  # Expected output: 14.0

    # Direct subscript access for asynchronous invocation
    add_func2 = registry["open_api_calculator-add_get"]
    result = await add_func2(7, 8)
    print(result)  # Expected output: 15.0


asyncio.run(call_async_add_func())


async def call_async_add_tool():
    # Retrieve the tool object for asynchronous invocation
    add_tool = registry.get_tool("open_api_calculator-add_get")
    result = await add_tool.arun({"a": 9, "b": 10})
    print(result)  # Expected output: 19.0


asyncio.run(call_async_add_tool())
