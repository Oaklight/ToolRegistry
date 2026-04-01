"""Integration tests for toolregistry package."""

import asyncio

import pytest

from toolregistry import ToolRegistry
from toolregistry.types import ChatCompletionMessageFunctionToolCall, Function


class TestToolRegistryIntegration:
    """Integration tests for ToolRegistry with various components."""

    def test_end_to_end_tool_registration_and_execution(self):
        """Test complete workflow from registration to execution."""
        registry = ToolRegistry(name="integration_test")

        # Define test functions
        def add_numbers(a: int, b: int) -> int:
            """Add two numbers together."""
            return a + b

        def multiply_numbers(x: float, y: float) -> float:
            """Multiply two numbers."""
            return x * y

        def greet_person(name: str, greeting: str = "Hello") -> str:
            """Greet a person with a custom greeting."""
            return f"{greeting}, {name}!"

        # Register functions
        registry.register(add_numbers)
        registry.register(multiply_numbers)
        registry.register(greet_person)

        # Verify registration
        assert "add_numbers" in registry
        assert "multiply_numbers" in registry
        assert "greet_person" in registry
        assert len(registry.list_tools()) == 3

        # Test JSON schema generation
        tools_json = registry.get_schemas()
        assert len(tools_json) == 3

        # Verify each tool has proper schema
        for tool_schema in tools_json:
            assert "type" in tool_schema
            assert tool_schema["type"] == "function"
            assert "function" in tool_schema
            assert "name" in tool_schema["function"]
            assert "description" in tool_schema["function"]
            assert "parameters" in tool_schema["function"]

        # Test tool execution via registry
        add_result = registry["add_numbers"](10, 20)
        multiply_result = registry["multiply_numbers"](2.5, 4.0)
        greet_result = registry["greet_person"]("Alice")

        assert add_result == 30
        assert multiply_result == 10.0
        assert greet_result == "Hello, Alice!"

    def test_tool_call_execution_workflow(self):
        """Test complete tool call execution workflow."""
        registry = ToolRegistry(name="tool_call_test")

        # Register functions
        def calculate_area(length: float, width: float) -> float:
            """Calculate area of rectangle."""
            return length * width

        def format_result(value: float, unit: str = "sq units") -> str:
            """Format a numeric result with units."""
            return f"{value:.2f} {unit}"

        registry.register(calculate_area)
        registry.register(format_result)

        # Create tool calls
        tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_1",
                function=Function(
                    name="calculate_area",
                    arguments='{"length": 5.0, "width": 3.0}',
                ),
            ),
            ChatCompletionMessageFunctionToolCall(
                id="call_2",
                function=Function(
                    name="format_result",
                    arguments='{"value": 15.0, "unit": "square meters"}',
                ),
            ),
        ]

        # Execute tool calls
        results = registry.execute_tool_calls(tool_calls)

        assert "call_1" in results
        assert "call_2" in results
        assert float(results["call_1"]) == 15.0
        assert results["call_2"] == "15.00 square meters"

        # Test message recovery
        messages = registry.build_tool_call_messages(tool_calls, results)

        assert len(messages) == 3  # Assistant message + 2 tool responses
        assert messages[0]["role"] == "assistant"
        assert "tool_calls" in messages[0]
        assert messages[1]["role"] == "tool"
        assert messages[2]["role"] == "tool"
        assert messages[1]["tool_call_id"] == "call_1"
        assert messages[2]["tool_call_id"] == "call_2"

    def test_namespace_management_workflow(self):
        """Test complete namespace management workflow."""
        registry = ToolRegistry(name="namespace_test")

        # Register functions with different namespaces
        def add(a: int, b: int) -> int:
            return a + b

        def subtract(a: int, b: int) -> int:
            return a - b

        def concat(s1: str, s2: str) -> str:
            return s1 + s2

        def upper(text: str) -> str:
            return text.upper()

        registry.register(add, namespace="math")
        registry.register(subtract, namespace="math")
        registry.register(concat, namespace="string")
        registry.register(upper, namespace="string")

        # Verify namespaced registration
        assert "math-add" in registry
        assert "math-subtract" in registry
        assert "string-concat" in registry
        assert "string-upper" in registry

    def test_registry_merging_workflow(self):
        """Test complete registry merging workflow."""
        # Create first registry with math functions
        math_registry = ToolRegistry(name="math")

        def add(a: int, b: int) -> int:
            return a + b

        def multiply(a: int, b: int) -> int:
            return a * b

        math_registry.register(add)
        math_registry.register(multiply)

        # Create second registry with string functions
        string_registry = ToolRegistry(name="string")

        def concat(s1: str, s2: str) -> str:
            return s1 + s2

        def reverse(text: str) -> str:
            return text[::-1]

        string_registry.register(concat)
        string_registry.register(reverse)

        # Create main registry and merge others
        main_registry = ToolRegistry(name="main")

        main_registry.merge(math_registry)
        main_registry.merge(string_registry)

        # Verify merged tools exist (prefixed with source registry name)
        actual_tools = main_registry.list_tools()
        assert len(actual_tools) >= 4

        # Merged tools should be callable
        for tool_name in actual_tools:
            assert main_registry.get_callable(tool_name) is not None

    @pytest.mark.asyncio
    async def test_async_tool_integration(self):
        """Test integration with async tools."""
        registry = ToolRegistry(name="async_test")

        # Define async function
        async def async_process(data: str, delay: float = 0.01) -> str:
            """Process data asynchronously."""
            await asyncio.sleep(delay)
            return f"processed: {data}"

        # Define sync function for comparison
        def sync_process(data: str) -> str:
            """Process data synchronously."""
            return f"sync: {data}"

        registry.register(async_process)
        registry.register(sync_process)

        # Verify async detection
        async_tool = registry.get_tool("async_process")
        sync_tool = registry.get_tool("sync_process")

        assert async_tool.is_async is True
        assert sync_tool.is_async is False

        # Test async execution
        async_result = await async_tool.arun({"data": "test_data"})
        sync_result = sync_tool.run({"data": "test_data"})

        assert async_result == "processed: test_data"
        assert sync_result == "sync: test_data"

    def test_error_handling_integration(self):
        """Test error handling across the system."""
        registry = ToolRegistry(name="error_test")

        # Function that raises an exception
        def failing_function(should_fail: bool = True) -> str:
            """Function that can fail."""
            if should_fail:
                raise ValueError("Intentional failure")
            return "success"

        # Function with invalid parameters
        def good_function(x: int, y: int) -> int:
            """Function that works correctly."""
            return x + y

        registry.register(failing_function)
        registry.register(good_function)

        # Test tool execution error handling
        failing_tool = registry.get_tool("failing_function")
        good_tool = registry.get_tool("good_function")

        # Test direct tool execution
        error_result = failing_tool.run({"should_fail": True})
        success_result = failing_tool.run({"should_fail": False})
        good_result = good_tool.run({"x": 5, "y": 3})

        assert "Error executing" in error_result
        assert success_result == "success"
        assert good_result == 8

        # Test tool call execution error handling
        tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_fail",
                function=Function(
                    name="failing_function", arguments='{"should_fail": true}'
                ),
            ),
            ChatCompletionMessageFunctionToolCall(
                id="call_good",
                function=Function(name="good_function", arguments='{"x": 10, "y": 20}'),
            ),
            ChatCompletionMessageFunctionToolCall(
                id="call_invalid",
                function=Function(name="nonexistent_function", arguments="{}"),
            ),
        ]

        results = registry.execute_tool_calls(tool_calls)

        assert "Error" in results["call_fail"]
        assert int(results["call_good"]) == 30
        assert (
            "not found" in results["call_invalid"].lower()
            or "Error" in results["call_invalid"]
        )

    def test_complex_parameter_validation_integration(self):
        """Test integration with complex parameter validation."""
        registry = ToolRegistry(name="validation_test")

        # Function with complex parameters
        def process_data(
            items: list[str],
            metadata: dict[str, int],
            threshold: float = 0.5,
            enabled: bool = True,
        ) -> dict[str, any]:
            """Process data with complex parameters."""
            return {
                "item_count": len(items),
                "metadata_keys": list(metadata.keys()),
                "threshold": threshold,
                "enabled": enabled,
            }

        registry.register(process_data)

        # Test with valid parameters
        tool = registry.get_tool("process_data")

        valid_params = {
            "items": ["a", "b", "c"],
            "metadata": {"key1": 1, "key2": 2},
            "threshold": 0.8,
            "enabled": False,
        }

        result = tool.run(valid_params)

        assert result["item_count"] == 3
        assert "key1" in result["metadata_keys"]
        assert "key2" in result["metadata_keys"]
        assert result["threshold"] == 0.8
        assert result["enabled"] is False

        # Test with minimal parameters (using defaults)
        minimal_params = {"items": ["x"], "metadata": {"test": 42}}

        result2 = tool.run(minimal_params)

        assert result2["item_count"] == 1
        assert result2["threshold"] == 0.5  # Default value
        assert result2["enabled"] is True  # Default value

    def test_different_api_formats_integration(self):
        """Test integration with different API formats."""
        registry = ToolRegistry(name="api_format_test")

        def simple_func(message: str) -> str:
            """Simple function for API format testing."""
            return f"Response: {message}"

        registry.register(simple_func)

        # Test different API formats
        openai_format = registry.get_schemas(api_format="openai-chat")
        openai_chat_format = registry.get_schemas(api_format="openai-chat")
        response_format = registry.get_schemas(api_format="openai-response")
        anthropic_format = registry.get_schemas(api_format="anthropic")
        gemini_format = registry.get_schemas(api_format="gemini")

        # Verify OpenAI formats
        assert openai_format[0]["type"] == "function"
        assert "function" in openai_format[0]

        assert openai_chat_format[0]["type"] == "function"
        assert "function" in openai_chat_format[0]

        # Verify Response format
        assert response_format[0]["type"] == "function"
        assert "name" in response_format[0]
        assert "strict" in response_format[0]
        assert response_format[0]["strict"] is False

        # Verify Anthropic format
        assert "name" in anthropic_format[0]
        assert "input_schema" in anthropic_format[0]

        # Verify Gemini format
        assert "name" in gemini_format[0]
        assert "parameters" in gemini_format[0]

        # Test that all formats contain the same function name
        for format_result in [openai_format, openai_chat_format]:
            assert format_result[0]["function"]["name"] == "simple_func"

        assert response_format[0]["name"] == "simple_func"
        assert anthropic_format[0]["name"] == "simple_func"
        assert gemini_format[0]["name"] == "simple_func"

    def test_execution_mode_integration(self):
        """Test integration with different execution modes."""
        registry = ToolRegistry(name="execution_mode_test")

        def cpu_intensive_task(n: int) -> int:
            """CPU intensive task for testing execution modes."""
            result = 0
            for i in range(n):
                result += i
            return result

        registry.register(cpu_intensive_task)

        # Test with different execution modes
        tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_1",
                function=Function(name="cpu_intensive_task", arguments='{"n": 1000}'),
            ),
            ChatCompletionMessageFunctionToolCall(
                id="call_2",
                function=Function(name="cpu_intensive_task", arguments='{"n": 2000}'),
            ),
        ]

        # Test thread mode
        registry.set_execution_mode("thread")
        thread_results = registry.execute_tool_calls(tool_calls)

        # Test process mode
        registry.set_execution_mode("process")
        process_results = registry.execute_tool_calls(tool_calls)

        # Results should be the same regardless of execution mode
        assert thread_results["call_1"] == process_results["call_1"]
        assert thread_results["call_2"] == process_results["call_2"]

        # Verify actual calculations
        expected_1 = sum(range(1000))
        expected_2 = sum(range(2000))

        assert int(thread_results["call_1"]) == expected_1
        assert int(thread_results["call_2"]) == expected_2
