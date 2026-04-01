"""Unit tests for the types module."""

import pytest

from toolregistry.types import (
    Function,
    ChatCompletionMessageFunctionToolCall,
    ChatCompetionMessageToolCallResult,
    ChatCompletionMessage,
    ResponseFunctionToolCall,
    ResponseFunctionToolCallResult,
    ToolCall,
    ToolCallResult,
    convert_tool_calls,
    recover_assistant_message,
    recover_tool_message,
)


class TestFunction:
    """Test cases for the Function class."""

    def test_function_creation(self):
        """Test creating a Function instance."""
        func = Function(name="test_function", arguments='{"param": "value"}')

        assert func.name == "test_function"
        assert func.arguments == '{"param": "value"}'

    def test_function_serialization(self):
        """Test Function serialization."""
        func = Function(name="test_function", arguments='{"param": "value"}')

        serialized = func.model_dump()

        assert serialized["name"] == "test_function"
        assert serialized["arguments"] == '{"param": "value"}'


class TestChatCompletionMessageFunctionToolCall:
    """Test cases for the ChatCompletionMessageFunctionToolCall class."""

    def test_tool_call_creation(self):
        """Test creating a ChatCompletionMessageFunctionToolCall instance."""
        tool_call = ChatCompletionMessageFunctionToolCall(
            id="call_123",
            function=Function(name="test_function", arguments='{"param": "value"}'),
        )

        assert tool_call.id == "call_123"
        assert tool_call.type == "function"
        assert tool_call.function.name == "test_function"

    def test_tool_call_default_type(self):
        """Test that type defaults to 'function'."""
        tool_call = ChatCompletionMessageFunctionToolCall(
            id="call_123", function=Function(name="test", arguments="{}")
        )

        assert tool_call.type == "function"

    def test_tool_call_serialization(self):
        """Test ChatCompletionMessageFunctionToolCall serialization."""
        tool_call = ChatCompletionMessageFunctionToolCall(
            id="call_123",
            function=Function(name="test_function", arguments='{"param": "value"}'),
        )

        serialized = tool_call.model_dump()

        assert serialized["id"] == "call_123"
        assert serialized["type"] == "function"
        assert serialized["function"]["name"] == "test_function"


class TestChatCompetionMessageToolCallResult:
    """Test cases for the ChatCompetionMessageToolCallResult class."""

    def test_tool_call_result_creation(self):
        """Test creating a ChatCompetionMessageToolCallResult instance."""
        result = ChatCompetionMessageToolCallResult(
            tool_call_id="call_123", content="Result content"
        )

        assert result.role == "tool"
        assert result.tool_call_id == "call_123"
        assert result.content == "Result content"

    def test_tool_call_result_default_role(self):
        """Test that role defaults to 'tool'."""
        result = ChatCompetionMessageToolCallResult(
            tool_call_id="call_123", content="Result content"
        )

        assert result.role == "tool"


class TestChatCompletionMessage:
    """Test cases for the ChatCompletionMessage class."""

    def test_message_creation_minimal(self):
        """Test creating a minimal ChatCompletionMessage."""
        message = ChatCompletionMessage()

        assert message.role == "assistant"
        assert message.content is None
        assert message.tool_calls is None

    def test_message_creation_with_content(self):
        """Test creating a ChatCompletionMessage with content."""
        message = ChatCompletionMessage(content="Hello, world!")

        assert message.content == "Hello, world!"
        assert message.role == "assistant"

    def test_message_creation_with_tool_calls(self):
        """Test creating a ChatCompletionMessage with tool calls."""
        tool_call = ChatCompletionMessageFunctionToolCall(
            id="call_123", function=Function(name="test", arguments="{}")
        )

        message = ChatCompletionMessage(tool_calls=[tool_call])

        assert len(message.tool_calls) == 1
        assert message.tool_calls[0].id == "call_123"


class TestResponseFunctionToolCall:
    """Test cases for the ResponseFunctionToolCall class."""

    def test_response_tool_call_creation(self):
        """Test creating a ResponseFunctionToolCall instance."""
        tool_call = ResponseFunctionToolCall(
            arguments='{"param": "value"}',
            call_id="call_123",
            name="test_function",
        )

        assert tool_call.arguments == '{"param": "value"}'
        assert tool_call.call_id == "call_123"
        assert tool_call.name == "test_function"
        assert tool_call.type == "function_call"

    def test_response_tool_call_with_optional_fields(self):
        """Test creating a ResponseFunctionToolCall with optional fields."""
        tool_call = ResponseFunctionToolCall(
            arguments='{"param": "value"}',
            call_id="call_123",
            name="test_function",
            id="fc_123",
            status="completed",
        )

        assert tool_call.id == "fc_123"
        assert tool_call.status == "completed"

    def test_response_tool_call_default_type(self):
        """Test that type defaults to 'function_call'."""
        tool_call = ResponseFunctionToolCall(
            arguments="{}", call_id="call_123", name="test"
        )

        assert tool_call.type == "function_call"


class TestResponseFunctionToolCallResult:
    """Test cases for the ResponseFunctionToolCallResult class."""

    def test_response_tool_call_result_creation(self):
        """Test creating a ResponseFunctionToolCallResult instance."""
        result = ResponseFunctionToolCallResult(
            call_id="call_123", output="Function output"
        )

        assert result.type == "function_call_output"
        assert result.call_id == "call_123"
        assert result.output == "Function output"

    def test_response_tool_call_result_default_type(self):
        """Test that type defaults to 'function_call_output'."""
        result = ResponseFunctionToolCallResult(call_id="call_123", output="output")

        assert result.type == "function_call_output"


class TestToolCall:
    """Test cases for the ToolCall class."""

    def test_tool_call_creation(self):
        """Test creating a ToolCall instance."""
        tool_call = ToolCall(
            id="call_123", name="test_function", arguments='{"param": "value"}'
        )

        assert tool_call.id == "call_123"
        assert tool_call.name == "test_function"
        assert tool_call.arguments == '{"param": "value"}'

    def test_from_tool_call_chat_completion_format(self):
        """Test converting from ChatCompletionMessageFunctionToolCall."""
        chat_tool_call = ChatCompletionMessageFunctionToolCall(
            id="call_123",
            function=Function(name="test_function", arguments='{"param": "value"}'),
        )

        tool_call = ToolCall.from_tool_call(chat_tool_call)

        assert tool_call.id == "call_123"
        assert tool_call.name == "test_function"
        assert tool_call.arguments == '{"param": "value"}'

    def test_from_tool_call_response_format(self):
        """Test converting from ResponseFunctionToolCall."""
        response_tool_call = ResponseFunctionToolCall(
            call_id="call_456", name="another_function", arguments='{"x": 10}'
        )

        tool_call = ToolCall.from_tool_call(response_tool_call)

        assert tool_call.id == "call_456"
        assert tool_call.name == "another_function"
        assert tool_call.arguments == '{"x": 10}'

    def test_from_tool_call_unsupported_type_raises_error(self):
        """Test that unsupported type raises TypeError."""
        with pytest.raises(TypeError, match="Unsupported tool call format"):
            ToolCall.from_tool_call("not_a_tool_call")


class TestToolCallResult:
    """Test cases for the ToolCallResult class."""

    def test_tool_call_result_creation(self):
        """Test creating a ToolCallResult instance."""
        result = ToolCallResult(id="call_123", result="Function result")

        assert result.id == "call_123"
        assert result.result == "Function result"

    def test_tool_call_result_serialization_converts_to_string(self):
        """Test that result field is converted to string during serialization."""
        result = ToolCallResult(id="call_123", result=42)

        serialized = result.model_dump()

        assert serialized["result"] == "42"

    def test_tool_call_result_complex_object_serialization(self):
        """Test serialization of complex objects."""

        class CustomObject:
            def __str__(self):
                return "custom_representation"

        result = ToolCallResult(id="call_123", result=CustomObject())

        serialized = result.model_dump()

        assert serialized["result"] == "custom_representation"


class TestConvertToolCalls:
    """Test cases for the convert_tool_calls function."""

    def test_convert_tool_calls_chat_completion_format(self):
        """Test converting chat completion format tool calls."""
        chat_tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_1",
                function=Function(name="func1", arguments='{"a": 1}'),
            ),
            ChatCompletionMessageFunctionToolCall(
                id="call_2",
                function=Function(name="func2", arguments='{"b": 2}'),
            ),
        ]

        converted = convert_tool_calls(chat_tool_calls)

        assert len(converted) == 2
        assert all(isinstance(tc, ToolCall) for tc in converted)
        assert converted[0].id == "call_1"
        assert converted[1].id == "call_2"

    def test_convert_tool_calls_response_format(self):
        """Test converting response format tool calls."""
        response_tool_calls = [
            ResponseFunctionToolCall(
                call_id="call_3", name="func3", arguments='{"c": 3}'
            )
        ]

        converted = convert_tool_calls(response_tool_calls)

        assert len(converted) == 1
        assert isinstance(converted[0], ToolCall)
        assert converted[0].id == "call_3"

    def test_convert_tool_calls_empty_list(self):
        """Test converting empty list."""
        converted = convert_tool_calls([])

        assert converted == []


class TestRecoverAssistantMessage:
    """Test cases for the recover_assistant_message function."""

    def test_recover_assistant_message_openai_format(self):
        """Test recovering assistant message in OpenAI format."""
        tool_calls = [
            ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')
        ]

        messages = recover_assistant_message(tool_calls, api_format="openai")

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert "tool_calls" in messages[0]
        assert len(messages[0]["tool_calls"]) == 1
        assert messages[0]["tool_calls"][0]["id"] == "call_1"

    def test_recover_assistant_message_openai_chatcompletion_format(self):
        """Test recovering assistant message in OpenAI chat completion format."""
        tool_calls = [
            ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')
        ]

        messages = recover_assistant_message(
            tool_calls, api_format="openai-chatcompletion"
        )

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert "tool_calls" in messages[0]

    def test_recover_assistant_message_openai_response_format(self):
        """Test recovering assistant message in OpenAI response format."""
        tool_calls = [
            ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')
        ]

        messages = recover_assistant_message(tool_calls, api_format="openai-response")

        assert len(messages) == 1
        assert messages[0]["call_id"] == "call_1"
        assert messages[0]["name"] == "test_function"
        assert messages[0]["type"] == "function_call"

    def test_recover_assistant_message_anthropic_format(self):
        """Test recovering assistant message in Anthropic format."""
        tool_calls = [
            ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')
        ]

        messages = recover_assistant_message(tool_calls, api_format="anthropic")

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert "content" in messages[0]
        assert messages[0]["content"][0]["type"] == "tool_use"
        assert messages[0]["content"][0]["name"] == "test_function"

    def test_recover_assistant_message_gemini_format(self):
        """Test recovering assistant message in Gemini format."""
        tool_calls = [
            ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')
        ]

        messages = recover_assistant_message(tool_calls, api_format="gemini")

        assert len(messages) == 1
        assert messages[0]["role"] == "model"
        assert "parts" in messages[0]
        assert "functionCall" in messages[0]["parts"][0]

    def test_recover_assistant_message_filters_invalid_tool_calls(self):
        """Test that invalid tool calls are filtered out."""
        tool_calls = [
            ToolCall(
                id="call_1", name="valid_function", arguments='{"param": "value"}'
            ),
            ToolCall(
                id="call_2", name="", arguments='{"param": "value"}'
            ),  # Empty name
            ToolCall(
                id="call_3", name="another_function", arguments=""
            ),  # Empty arguments
        ]

        messages = recover_assistant_message(tool_calls, api_format="openai")

        assert len(messages) == 1
        assert len(messages[0]["tool_calls"]) == 1  # Only valid tool call
        assert messages[0]["tool_calls"][0]["id"] == "call_1"

    def test_recover_assistant_message_unsupported_format_raises_error(self):
        """Test that unsupported format raises ValueError."""
        tool_calls = [ToolCall(id="call_1", name="test", arguments="{}")]

        with pytest.raises(ValueError, match="Unsupported API format"):
            recover_assistant_message(tool_calls, api_format="unsupported")


class TestRecoverToolMessage:
    """Test cases for the recover_tool_message function."""

    def test_recover_tool_message_openai_format(self):
        """Test recovering tool message in OpenAI format."""
        tool_responses = {"call_1": "Result 1", "call_2": "Result 2"}

        messages = recover_tool_message(tool_responses, api_format="openai")

        assert len(messages) == 2

        for message in messages:
            assert message["role"] == "tool"
            assert "tool_call_id" in message
            assert "content" in message

        # Check specific content
        call_ids = [msg["tool_call_id"] for msg in messages]
        assert "call_1" in call_ids
        assert "call_2" in call_ids

    def test_recover_tool_message_openai_chatcompletion_format(self):
        """Test recovering tool message in OpenAI chat completion format."""
        tool_responses = {"call_1": "Result"}

        messages = recover_tool_message(
            tool_responses, api_format="openai-chatcompletion"
        )

        assert len(messages) == 1
        assert messages[0]["role"] == "tool"
        assert messages[0]["tool_call_id"] == "call_1"
        assert messages[0]["content"] == "Result"

    def test_recover_tool_message_openai_response_format(self):
        """Test recovering tool message in OpenAI response format."""
        tool_responses = {"call_1": "Result"}

        messages = recover_tool_message(tool_responses, api_format="openai-response")

        assert len(messages) == 1
        assert messages[0]["type"] == "function_call_output"
        assert messages[0]["call_id"] == "call_1"
        assert messages[0]["output"] == "Result"

    def test_recover_tool_message_anthropic_format(self):
        """Test recovering tool message in Anthropic format."""
        tool_responses = {"call_1": "result"}

        messages = recover_tool_message(tool_responses, api_format="anthropic")

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "content" in messages[0]
        assert messages[0]["content"][0]["type"] == "tool_result"
        assert messages[0]["content"][0]["tool_use_id"] == "call_1"

    def test_recover_tool_message_gemini_format(self):
        """Test recovering tool message in Gemini format."""
        tool_responses = {"call_1": "result"}

        messages = recover_tool_message(tool_responses, api_format="gemini")

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "parts" in messages[0]
        assert "functionResponse" in messages[0]["parts"][0]

    def test_recover_tool_message_converts_non_string_results(self):
        """Test that non-string results are converted to strings."""
        tool_responses = {
            "call_1": 42,
            "call_2": {"key": "value"},
            "call_3": [1, 2, 3],
        }

        messages = recover_tool_message(tool_responses, api_format="openai")

        assert len(messages) == 3

        for message in messages:
            assert isinstance(message["content"], str)

    def test_recover_tool_message_unsupported_format_raises_error(self):
        """Test that unsupported format raises ValueError."""
        tool_responses = {"call_1": "result"}

        with pytest.raises(ValueError, match="Unsupported API format"):
            recover_tool_message(tool_responses, api_format="unsupported")

    def test_recover_tool_message_empty_responses(self):
        """Test recovering tool message with empty responses."""
        tool_responses = {}

        messages = recover_tool_message(tool_responses, api_format="openai")

        assert messages == []
