# common/tools.py
import json
from pprint import pprint

from toolregistry import ToolRegistry

# Create a global instance of the ToolRegistry
tool_registry = ToolRegistry()

# Example usage
if __name__ == "__main__":

    @tool_registry.register
    def get_weather(location: str, void_param: None = None) -> str:
        """Get the current weather for a given location."""
        return f"Weather in {location}: Sunny, 25°C"

    @tool_registry.register
    def calculate_price(price: float, discount: float = 0.1) -> float:
        """Calculate final price with optional discount."""
        return price * (1 - discount)

    @tool_registry.register
    def format_name(first: str, last: str, middle: str = None) -> str:
        """Format a full name with optional middle name."""
        return f"{first} {middle + ' ' if middle else ''}{last}"

    def process_data(data: dict, strict: bool = True) -> str:
        """Process data with strict mode flag."""
        return "Strict processing" if strict else "Loose processing"

    tool_registry.register(process_data)

    # Get the JSON representation of all tools
    print("Tools JSON:")
    pprint(tool_registry)

    # Get a callable function by name
    print("\nCalling 'get_weather':")
    get_weather_fn = tool_registry["get_weather"]
    print(tool_registry["get_weather"]("San Francisco"))
    print(get_weather_fn("New York"))

    # Test the new Tool.run method
    print("\nTesting Tool.run method:")

    # Test get_weather
    weather_tool = tool_registry._tools["get_weather"]
    print("1. get_weather normal call:")
    print(weather_tool.run({"location": "New York"}))
    print("\n2. get_weather invalid type:")
    print(weather_tool.run({"location": 123}))
    print("\n3. get_weather missing required:")
    print(weather_tool.run({}))

    # Test calculate_price
    price_tool = tool_registry._tools["calculate_price"]
    print("\n4. calculate_price with default:")
    print(price_tool.run({"price": 100}))
    print("\n5. calculate_price custom discount:")
    print(price_tool.run({"price": 100, "discount": 0.2}))
    print("\n6. calculate_price invalid discount:")
    print(price_tool.run({"price": 100, "discount": "20%"}))

    # Test format_name
    name_tool = tool_registry._tools["format_name"]
    print("\n7. format_name without middle:")
    print(name_tool.run({"first": "John", "last": "Doe"}))
    print("\n8. format_name with middle:")
    print(name_tool.run({"first": "John", "middle": "Q", "last": "Doe"}))
    print("\n9. format_name invalid middle:")
    print(name_tool.run({"first": "John", "middle": 123, "last": "Doe"}))

    # Test process_data
    data_tool = tool_registry._tools["process_data"]
    print("\n10. process_data strict mode:")
    print(data_tool.run({"data": {"key": "value"}}))
    print("\n11. process_data loose mode:")
    print(data_tool.run({"data": {"key": "value"}, "strict": False}))
    print("\n12. process_data invalid strict:")
    print(data_tool.run({"data": {"key": "value"}, "strict": "yes"}))

    # Add async function for testing
    @tool_registry.register
    async def async_echo(message: str) -> str:
        """Async echo function for testing."""
        await asyncio.sleep(10)  # Simulate async work
        return f"Echo: {message}"

    # Async test functions
    async def test_async_tool():
        try:
            print("\nTesting async tool...")
            echo_tool = tool_registry._tools["async_echo"]
            result = await echo_tool.arun({"message": "test async call"})
            print(f"Async call result: {result}")
            return True
        except Exception as e:
            print(f"Error: {str(e)}")
            return False

    # Run async tests
    import asyncio

    asyncio.run(test_async_tool())
