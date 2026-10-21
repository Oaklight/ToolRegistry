"""Pytest configuration and fixtures for toolregistry tests."""

import gc
import weakref

import pytest

from toolregistry import Tool, ToolRegistry
from toolregistry._async_runtime import AsyncRuntime


# ---------------------------------------------------------------------------
# Execution-resource hygiene (#311)
#
# ToolRegistry owns a thread pool and a process pool.  Pools are created
# lazily, but a test that executes through one leaves its workers alive until
# the registry is closed or garbage-collected.  Leaked workers keep pytest's
# capture file descriptors open, which is what made the suite stall.  Track
# every instance and close the survivors at module teardown.
# ---------------------------------------------------------------------------

_registries: "weakref.WeakSet[ToolRegistry]" = weakref.WeakSet()
_original_init = ToolRegistry.__init__


def _tracking_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    _registries.add(self)


ToolRegistry.__init__ = _tracking_init


@pytest.fixture(scope="module", autouse=True)
def _close_leaked_registries():
    """Close registries a test module did not close itself."""
    yield
    for registry in list(_registries):
        try:
            registry.close()
        except Exception:
            # Teardown must not mask a real test failure.
            pass
    _registries.clear()
    # Stop the shared loop as well: a leaked task (for example an MCP
    # transport reconnecting after its server exited) can otherwise keep
    # spinning for the rest of the session and hold capture fds.  The next
    # module recreates the loop lazily.
    AsyncRuntime.shutdown()
    gc.collect()


@pytest.fixture
def sample_function():
    """Sample function for testing."""

    def add_numbers(a: int, b: int) -> int:
        """Add two numbers together.

        Args:
            a: First number
            b: Second number

        Returns:
            Sum of a and b
        """
        return a + b

    return add_numbers


@pytest.fixture
def async_sample_function():
    """Sample async function for testing."""
    import asyncio

    async def async_add_numbers(a: int, b: int) -> int:
        """Add two numbers together asynchronously.

        Args:
            a: First number
            b: Second number

        Returns:
            Sum a and b
        """
        await asyncio.sleep(0.01)  # Simulate async work
        return a + b

    return async_add_numbers


@pytest.fixture
def sample_tool(sample_function):
    """Sample Tool instance for testing."""
    return Tool.from_function(sample_function)


@pytest.fixture
def sample_registry():
    """Sample ToolRegistry instance for testing."""
    return ToolRegistry(name="test_registry")


@pytest.fixture
def populated_registry(sample_registry, sample_function):
    """ToolRegistry with some tools registered."""
    sample_registry.register(sample_function)

    def multiply_numbers(x: float, y: float) -> float:
        """Multiply two numbers."""
        return x * y

    sample_registry.register(multiply_numbers)
    return sample_registry


@pytest.fixture
def sample_tool_call_data():
    """Sample tool call data for testing."""
    return {
        "id": "call_123",
        "name": "add_numbers",
        "arguments": '{"a": 5, "b": 3}',
    }


@pytest.fixture
def sample_openai_tool_call():
    """Sample OpenAI tool call format."""
    return {
        "id": "call_abc123",
        "type": "function",
        "function": {"name": "add_numbers", "arguments": '{"a": 10, "b": 20}'},
    }


@pytest.fixture
def sample_response_tool_call():
    """Sample Response API tool call format."""
    return {
        "call_id": "call_def456",
        "type": "function_call",
        "name": "multiply_numbers",
        "arguments": '{"x": 2.5, "y": 4.0}',
    }


class MockClass:
    """Mock class for testing class-based tool registration."""

    @staticmethod
    def static_method(value: str) -> str:
        """A static method for testing."""
        return f"processed: {value}"

    def instance_method(self, value: int) -> int:
        """An instance method for testing."""
        return value * 2


@pytest.fixture
def mock_class():
    """Mock class instance for testing."""
    return MockClass()


@pytest.fixture
def mock_class_type():
    """Mock class type for testing."""
    return MockClass
