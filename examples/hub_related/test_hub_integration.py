"""Test cases for hub integration functionality."""

from toolregistry import ToolRegistry
from toolregistry.hub import Calculator, FileOps


def test_register_static_tools():
    """Test registering static methods from a class."""
    registry = ToolRegistry()
    registry.register_static_tools(Calculator)
    print(registry.get_available_tools())
    registry.register_static_tools(FileOps)
    print(registry.get_available_tools())

    # Verify all static methods are registered in _tools
    assert "add" in registry._tools
    assert "subtract" in registry._tools
    assert "multiply" in registry._tools
    assert "divide" in registry._tools

    # Verify method calls work
    assert registry._tools["add"].callable(2, 3) == 5
    assert registry._tools["subtract"].callable(5, 3) == 2
    assert registry._tools["multiply"].callable(2, 3) == 6
    assert registry._tools["divide"].callable(6, 3) == 2


async def test_register_static_tools_async():
    """Test async registration of static methods."""
    registry = ToolRegistry()
    await registry.register_static_tools_async(Calculator)

    # Verify methods are registered
    assert "Calculator.add" in registry
    assert registry["Calculator.add"](2, 3) == 5


if __name__ == "__main__":
    test_register_static_tools()
    print("All hub integration tests passed!")
