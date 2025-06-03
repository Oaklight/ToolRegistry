import asyncio
from toolregistry import ToolRegistry


class StaticExample:
    @staticmethod
    def greet(name: str) -> str:
        return f"Hello, {name}!"


class InstanceExample:
    def __init__(self, name: str):
        self.name = name

    def greet(self, name: str) -> str:
        return f"Hello, {name}! I'm {self.name}."


registry = ToolRegistry()
registry.register_from_class(StaticExample, with_namespace=True)
print(registry.get_available_tools())  # ['static_example.greet']
print(registry["static_example-greet"]("Alice"))  # Hello, Alice!


async def test_register_from_class_async():
    """Test async registration of static methods."""
    return await registry.register_from_class_async(
        InstanceExample("Bob"), with_namespace=True
    )


registry = ToolRegistry()
asyncio.run(test_register_from_class_async())
print(registry.get_available_tools())  # ['instance_example.greet']
print(registry["instance_example-greet"]("Alice"))  # Hello, Alice! I'm Bob.
