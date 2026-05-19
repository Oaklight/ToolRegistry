"""Unit tests for the llm.tool_calls module."""

import pytest

from toolregistry.llm.tool_calls import (
    ToolCall,
    ToolCallResult,
    build_assistant_message,
    build_tool_response,
    convert_tool_calls,
)

# ---------------------------------------------------------------------------
# Fixtures: provider-format dicts (no Pydantic models needed)
# ---------------------------------------------------------------------------

OAI_CHAT_TC = {
    "id": "call_123",
    "type": "function",
    "function": {"name": "test_function", "arguments": '{"param": "value"}'},
}

OAI_RESP_TC = {
    "type": "function_call",
    "call_id": "call_456",
    "name": "another_function",
    "arguments": '{"x": 10}',
}

ANTHROPIC_TC = {
    "type": "tool_use",
    "id": "tu_789",
    "name": "anthropic_func",
    "input": {"y": 20},
}

GEMINI_TC = {
    "functionCall": {"name": "gemini_func", "args": {"z": 30}},
}


# ---------------------------------------------------------------------------
# ToolCall
# ---------------------------------------------------------------------------


class TestToolCall:
    """Test cases for the ToolCall class."""

    def test_tool_call_creation(self):
        """Test creating a ToolCall instance directly."""
        tc = ToolCall(id="call_123", name="test_function", arguments='{"param": "value"}')

        assert tc.id == "call_123"
        assert tc.name == "test_function"
        assert tc.arguments == '{"param": "value"}'

    def test_from_tool_call_openai_chat_dict(self):
        """Test converting from OpenAI chat completion dict."""
        tc = ToolCall.from_tool_call(OAI_CHAT_TC)

        assert tc.id == "call_123"
        assert tc.name == "test_function"
        assert tc.arguments == '{"param": "value"}'

    def test_from_tool_call_openai_response_dict(self):
        """Test converting from OpenAI response API dict."""
        tc = ToolCall.from_tool_call(OAI_RESP_TC)

        assert tc.id == "call_456"
        assert tc.name == "another_function"
        assert tc.arguments == '{"x": 10}'

    def test_from_tool_call_anthropic_dict(self):
        """Test converting from Anthropic tool_use dict."""
        tc = ToolCall.from_tool_call(ANTHROPIC_TC)

        assert tc.id == "tu_789"
        assert tc.name == "anthropic_func"

    def test_from_tool_call_gemini_dict(self):
        """Test converting from Gemini functionCall dict."""
        tc = ToolCall.from_tool_call(GEMINI_TC)

        assert tc.name == "gemini_func"

    def test_from_tool_call_unsupported_raises_error(self):
        """Test that unsupported format raises TypeError."""
        with pytest.raises(TypeError, match="Unsupported tool call format"):
            ToolCall.from_tool_call("not_a_tool_call")


# ---------------------------------------------------------------------------
# ToolCallResult
# ---------------------------------------------------------------------------


class TestToolCallResult:
    """Test cases for the ToolCallResult class."""

    def test_tool_call_result_creation(self):
        tc = ToolCallResult(id="call_123", result="Function result")

        assert tc.id == "call_123"
        assert tc.result == "Function result"

    def test_tool_call_result_serialization_converts_to_string(self):
        result = ToolCallResult(id="call_123", result=42)

        serialized = result.model_dump()

        assert serialized["result"] == "42"

    def test_tool_call_result_complex_object_serialization(self):
        class CustomObject:
            def __str__(self):
                return "custom_representation"

        result = ToolCallResult(id="call_123", result=CustomObject())

        assert result.model_dump()["result"] == "custom_representation"


# ---------------------------------------------------------------------------
# convert_tool_calls
# ---------------------------------------------------------------------------


class TestConvertToolCalls:
    """Test cases for the convert_tool_calls function."""

    def test_convert_openai_chat_format(self):
        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "func1", "arguments": '{"a": 1}'}},
            {"id": "call_2", "type": "function", "function": {"name": "func2", "arguments": '{"b": 2}'}},
        ]

        converted = convert_tool_calls(tool_calls)

        assert len(converted) == 2
        assert all(isinstance(tc, ToolCall) for tc in converted)
        assert converted[0].id == "call_1"
        assert converted[1].id == "call_2"

    def test_convert_openai_response_format(self):
        tool_calls = [
            {"type": "function_call", "call_id": "call_3", "name": "func3", "arguments": '{"c": 3}'},
        ]

        converted = convert_tool_calls(tool_calls)

        assert len(converted) == 1
        assert converted[0].id == "call_3"

    def test_convert_empty_list(self):
        assert convert_tool_calls([]) == []


# ---------------------------------------------------------------------------
# build_assistant_message
# ---------------------------------------------------------------------------


class TestBuildAssistantMessage:
    """Test cases for the build_assistant_message function."""

    def test_openai_chat_format(self):
        tool_calls = [ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')]

        messages = build_assistant_message(tool_calls, api_format="openai-chat")

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert "tool_calls" in messages[0]
        assert messages[0]["tool_calls"][0]["id"] == "call_1"

    def test_openai_response_format(self):
        tool_calls = [ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')]

        messages = build_assistant_message(tool_calls, api_format="openai-response")

        assert len(messages) == 1
        assert messages[0]["call_id"] == "call_1"
        assert messages[0]["name"] == "test_function"
        assert messages[0]["type"] == "function_call"

    def test_anthropic_format(self):
        tool_calls = [ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')]

        messages = build_assistant_message(tool_calls, api_format="anthropic")

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"][0]["type"] == "tool_use"
        assert messages[0]["content"][0]["name"] == "test_function"

    def test_gemini_format(self):
        tool_calls = [ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')]

        messages = build_assistant_message(tool_calls, api_format="gemini")

        assert len(messages) == 1
        assert messages[0]["role"] == "model"
        assert "functionCall" in messages[0]["parts"][0]

    def test_filters_invalid_tool_calls(self):
        """Empty name or arguments are skipped."""
        tool_calls = [
            ToolCall(id="call_1", name="valid", arguments='{"x": 1}'),
            ToolCall(id="call_2", name="", arguments='{"x": 1}'),
            ToolCall(id="call_3", name="valid2", arguments=""),
        ]

        messages = build_assistant_message(tool_calls, api_format="openai-chat")

        assert len(messages[0]["tool_calls"]) == 1
        assert messages[0]["tool_calls"][0]["id"] == "call_1"

    def test_unsupported_format_raises_error(self):
        tool_calls = [ToolCall(id="call_1", name="test", arguments="{}")]

        with pytest.raises(ValueError, match="Unsupported API format"):
            build_assistant_message(tool_calls, api_format="unsupported")


# ---------------------------------------------------------------------------
# build_tool_response
# ---------------------------------------------------------------------------


class TestBuildToolResponse:
    """Test cases for the build_tool_response function."""

    def test_openai_chat_format(self):
        messages = build_tool_response(
            {"call_1": "Result 1", "call_2": "Result 2"}, api_format="openai-chat"
        )

        assert len(messages) == 2
        for msg in messages:
            assert msg["role"] == "tool"
            assert "tool_call_id" in msg
            assert "content" in msg
        call_ids = [m["tool_call_id"] for m in messages]
        assert "call_1" in call_ids
        assert "call_2" in call_ids

    def test_openai_chat_content(self):
        messages = build_tool_response({"call_1": "Result"}, api_format="openai-chat")

        assert messages[0]["tool_call_id"] == "call_1"
        assert messages[0]["content"] == "Result"

    def test_openai_response_format(self):
        messages = build_tool_response({"call_1": "Result"}, api_format="openai-response")

        assert len(messages) == 1
        assert messages[0]["type"] == "function_call_output"
        assert messages[0]["call_id"] == "call_1"
        assert messages[0]["output"] == "Result"

    def test_anthropic_format(self):
        messages = build_tool_response({"call_1": "result"}, api_format="anthropic")

        assert messages[0]["role"] == "user"
        assert messages[0]["content"][0]["type"] == "tool_result"
        assert messages[0]["content"][0]["tool_use_id"] == "call_1"

    def test_gemini_format(self):
        tool_calls = [ToolCall(id="call_1", name="my_func", arguments="{}")]
        messages = build_tool_response(
            {"call_1": "result"}, api_format="gemini", tool_calls=tool_calls
        )

        assert messages[0]["role"] == "user"
        assert "functionResponse" in messages[0]["parts"][0]
        assert messages[0]["parts"][0]["functionResponse"]["name"] == "my_func"

    def test_non_string_results_converted(self):
        messages = build_tool_response(
            {"call_1": 42, "call_2": {"key": "val"}, "call_3": [1, 2, 3]},
            api_format="openai-chat",
        )

        assert len(messages) == 3
        for msg in messages:
            assert isinstance(msg["content"], str)

    def test_unsupported_format_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported API format"):
            build_tool_response({"call_1": "result"}, api_format="unsupported")

    def test_empty_responses(self):
        assert build_tool_response({}, api_format="openai-chat") == []
