# common/tools.py
import json
from pprint import pprint

from toolregistry import ToolRegistry

# Create a global instance of the ToolRegistry
tool_registry = ToolRegistry()

# Example usage
if __name__ == "__main__":
    from cicada.tools.code_dochelper import doc_helper

    # Register a function
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    tool_registry.register(add)

    def get_weather(location: str, void_param: None = None) -> str:
        """Get the current weather for a given location."""
        return f"Weather in {location}: Sunny, 25°C"

    tool_registry.register(get_weather)

    # Register another function
    def get_news(topic: str) -> str:
        """Get the latest news on a given topic."""
        return f"Latest news about {topic}."

    tool_registry.register(get_news)

    # Get the JSON representation of all tools
    print("Tools JSON:")
    pprint(tool_registry)

    # Get a callable function by name
    print("\nCalling 'get_weather':")
    print(tool_registry["get_weather"]("San Francisco"))

    # Import and register another function

    tool_registry.register(doc_helper)

    # Get the JSON representation of all tools again
    print("\nUpdated Tools JSON:")
    print(json.dumps(tool_registry.get_tools_json(), indent=2))

    # Call the 'doc_helper' function
    print("\nCalling 'doc_helper':")
    pprint(tool_registry["doc_helper"]("build123d.Box", with_docstring=False))

    print(len(tool_registry))
