"""Unit tests for the llm.tool_calls module."""

import pytest

from toolregistry.llm.tool_calls import (
    ResultList,
    ToolCall,
    ToolCallResult,
    build_assistant_messages,
    build_tool_result_messages,
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
        tc = ToolCall(
            id="call_123", name="test_function", arguments='{"param": "value"}'
        )

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

    def test_to_ir(self):
        """Test converting ToolCall to rosetta IR ToolCallPart."""
        tc = ToolCall(id="c1", name="fn", arguments='{"x": 1}')
        ir = tc.to_ir()

        assert ir["type"] == "tool_call"
        assert ir["tool_call_id"] == "c1"
        assert ir["tool_name"] == "fn"
        assert ir["tool_input"] == {"x": 1}
        assert ir["tool_type"] == "function"

    def test_from_ir(self):
        """Test creating ToolCall from rosetta IR ToolCallPart."""
        ir = {
            "type": "tool_call",
            "tool_call_id": "c1",
            "tool_name": "fn",
            "tool_input": {"x": 1},
            "tool_type": "function",
        }
        tc = ToolCall.from_ir(ir)

        assert tc.id == "c1"
        assert tc.name == "fn"
        assert tc.arguments == '{"x": 1}'
        assert tc.type == "function"

    def test_to_ir_from_ir_roundtrip(self):
        """Test that to_ir -> from_ir preserves data."""
        tc = ToolCall(id="c1", name="fn", arguments='{"a": 1, "b": "hello"}')
        tc2 = ToolCall.from_ir(tc.to_ir())

        assert tc2.id == tc.id
        assert tc2.name == tc.name
        assert tc2.arguments == tc.arguments

    def test_convert_tool_calls_shortcircuit(self):
        """Test that convert_tool_calls passes through ToolCall instances."""
        from toolregistry.llm.tool_calls import convert_tool_calls

        tc = ToolCall(id="c1", name="fn", arguments='{"x": 42}')
        converted = convert_tool_calls([tc])

        assert converted[0] is tc
        assert converted[0].arguments == '{"x": 42}'


# ---------------------------------------------------------------------------
# ToolCallResult
# ---------------------------------------------------------------------------


class TestToolCallResult:
    """Test cases for the ToolCallResult dataclass."""

    def _make_tc(self, call_id="call_123"):
        return ToolCall(id=call_id, name="test_fn", arguments="{}")

    def test_tool_call_result_creation(self):
        tc = ToolCallResult(id="call_123", name="test_fn", result="Function result")

        assert tc.id == "call_123"
        assert tc.name == "test_fn"
        assert tc.result == "Function result"

    def test_tool_call_result_with_list(self):
        blocks = [{"type": "text", "text": "hello"}]
        tc = ToolCallResult(id="call_123", name="test_fn", result=blocks)

        assert tc.result == blocks

    def test_tool_call_result_frozen(self):
        tc = ToolCallResult(id="call_123", name="test_fn", result="ok")
        import pytest

        with pytest.raises(AttributeError):
            tc.result = "changed"


class TestErrorResult:
    """Test cases for the ErrorResult dataclass."""

    def _make_tc(self, call_id="call_err"):
        return ToolCall(id=call_id, name="fail_fn", arguments="{}")

    def test_error_result_creation(self):
        from toolregistry.llm.tool_calls import ErrorResult

        err = ErrorResult(id="call_err", name="fail_fn", message="ValueError: boom")

        assert err.id == "call_err"
        assert err.name == "fail_fn"
        assert err.message == "ValueError: boom"

    def test_error_result_str_is_json(self):
        from toolregistry.llm.tool_calls import ErrorResult

        err = ErrorResult(id="call_err", name="fail_fn", message="oops")
        assert str(err) == "oops"


class TestResultList:
    """Test cases for the ResultList helper."""

    def test_by_id_lookup(self):
        r1 = ToolCallResult(id="c1", name="fn", result="ok")
        r2 = ToolCallResult(id="c2", name="fn", result="42")
        rl = ResultList([r1, r2])

        assert rl.by_id("c1").result == "ok"
        assert rl.by_id("c2").result == "42"

    def test_getitem_string_key(self):
        r1 = ToolCallResult(id="c1", name="fn", result="ok")
        rl = ResultList([r1])

        assert rl["c1"].result == "ok"
        assert rl[0].result == "ok"

    def test_contains_string_key(self):
        r1 = ToolCallResult(id="c1", name="fn", result="ok")
        rl = ResultList([r1])

        assert "c1" in rl
        assert "missing" not in rl

    def test_by_id_missing_raises_keyerror(self):
        rl = ResultList([])
        with pytest.raises(KeyError):
            rl.by_id("missing")

    def test_is_list_subclass(self):
        rl = ResultList([])
        assert isinstance(rl, list)

    def test_iteration(self):
        r1 = ToolCallResult(id="c1", name="fn", result="a")
        r2 = ToolCallResult(id="c2", name="fn", result="b")
        rl = ResultList([r1, r2])

        assert [r.result for r in rl] == ["a", "b"]


# ---------------------------------------------------------------------------
# convert_tool_calls
# ---------------------------------------------------------------------------


class TestConvertToolCalls:
    """Test cases for the convert_tool_calls function."""

    def test_convert_openai_chat_format(self):
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "func1", "arguments": '{"a": 1}'},
            },
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "func2", "arguments": '{"b": 2}'},
            },
        ]

        converted = convert_tool_calls(tool_calls)

        assert len(converted) == 2
        assert all(isinstance(tc, ToolCall) for tc in converted)
        assert converted[0].id == "call_1"
        assert converted[1].id == "call_2"

    def test_convert_openai_response_format(self):
        tool_calls = [
            {
                "type": "function_call",
                "call_id": "call_3",
                "name": "func3",
                "arguments": '{"c": 3}',
            },
        ]

        converted = convert_tool_calls(tool_calls)

        assert len(converted) == 1
        assert converted[0].id == "call_3"

    def test_convert_empty_list(self):
        assert convert_tool_calls([]) == []


# ---------------------------------------------------------------------------
# build_assistant_messages
# ---------------------------------------------------------------------------


class TestBuildAssistantMessage:
    """Test cases for the build_assistant_messages function."""

    def test_openai_chat_format(self):
        tool_calls = [
            ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')
        ]

        messages = build_assistant_messages(tool_calls, api_format="openai-chat")

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert "tool_calls" in messages[0]
        assert messages[0]["tool_calls"][0]["id"] == "call_1"

    def test_openai_response_format(self):
        tool_calls = [
            ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')
        ]

        messages = build_assistant_messages(tool_calls, api_format="openai-responses")

        assert len(messages) == 1
        assert messages[0]["call_id"] == "call_1"
        assert messages[0]["name"] == "test_function"
        assert messages[0]["type"] == "function_call"

    def test_anthropic_format(self):
        tool_calls = [
            ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')
        ]

        messages = build_assistant_messages(tool_calls, api_format="anthropic")

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"][0]["type"] == "tool_use"
        assert messages[0]["content"][0]["name"] == "test_function"

    def test_gemini_format(self):
        tool_calls = [
            ToolCall(id="call_1", name="test_function", arguments='{"param": "value"}')
        ]

        messages = build_assistant_messages(tool_calls, api_format="gemini")

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

        messages = build_assistant_messages(tool_calls, api_format="openai-chat")

        assert len(messages[0]["tool_calls"]) == 1
        assert messages[0]["tool_calls"][0]["id"] == "call_1"

    def test_unsupported_format_raises_error(self):
        tool_calls = [ToolCall(id="call_1", name="test", arguments="{}")]

        with pytest.raises(ValueError, match="Unsupported API format"):
            build_assistant_messages(tool_calls, api_format="unsupported")


# ---------------------------------------------------------------------------
# build_tool_result_messages
# ---------------------------------------------------------------------------


class TestBuildToolResponse:
    """Test cases for the build_tool_result_messages function."""

    def test_openai_chat_format(self):
        messages = build_tool_result_messages(
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
        messages = build_tool_result_messages(
            {"call_1": "Result"}, api_format="openai-chat"
        )

        assert messages[0]["tool_call_id"] == "call_1"
        assert messages[0]["content"] == "Result"

    def test_openai_response_format(self):
        messages = build_tool_result_messages(
            {"call_1": "Result"}, api_format="openai-responses"
        )

        assert len(messages) == 1
        assert messages[0]["type"] == "function_call_output"
        assert messages[0]["call_id"] == "call_1"
        assert messages[0]["output"] == "Result"

    def test_anthropic_format(self):
        messages = build_tool_result_messages(
            {"call_1": "result"}, api_format="anthropic"
        )

        assert messages[0]["role"] == "user"
        assert messages[0]["content"][0]["type"] == "tool_result"
        assert messages[0]["content"][0]["tool_use_id"] == "call_1"

    def test_gemini_format(self):
        tool_calls = [ToolCall(id="call_1", name="my_func", arguments="{}")]
        messages = build_tool_result_messages(
            {"call_1": "result"}, api_format="gemini", tool_calls=tool_calls
        )

        assert messages[0]["role"] == "user"
        assert "functionResponse" in messages[0]["parts"][0]
        assert messages[0]["parts"][0]["functionResponse"]["name"] == "my_func"

    def test_non_string_results_converted(self):
        messages = build_tool_result_messages(
            {"call_1": 42, "call_2": {"key": "val"}, "call_3": [1, 2, 3]},
            api_format="openai-chat",
        )

        assert len(messages) == 3
        for msg in messages:
            assert isinstance(msg["content"], str)

    def test_unsupported_format_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported API format"):
            build_tool_result_messages({"call_1": "result"}, api_format="unsupported")

    def test_empty_responses(self):
        assert build_tool_result_messages({}, api_format="openai-chat") == []


# ---------------------------------------------------------------------------
# Deprecated aliases
# ---------------------------------------------------------------------------


class TestDeprecatedAliases:
    """Verify deprecated function aliases emit DeprecationWarning."""

    def test_build_assistant_message_deprecated(self):
        from toolregistry.llm.tool_calls import build_assistant_message

        tc = [ToolCall(id="c1", name="fn", arguments='{"x": 1}')]
        with pytest.warns(DeprecationWarning, match="build_assistant_messages"):
            build_assistant_message(tc, api_format="openai-chat")

    def test_build_tool_response_deprecated(self):
        from toolregistry.llm.tool_calls import build_tool_response

        with pytest.warns(DeprecationWarning, match="build_tool_result_messages"):
            build_tool_response({"c1": "ok"}, api_format="openai-chat")

    def test_expand_content_blocks_deprecated(self):
        from toolregistry.llm.content_blocks import expand_content_blocks

        with pytest.warns(DeprecationWarning, match="extract_multimodal_content"):
            expand_content_blocks({"c1": "text"})

    def test_build_expanded_user_message_deprecated(self):
        from toolregistry.llm.content_blocks import build_expanded_user_message

        parts = [{"type": "text", "text": "hello"}]
        with pytest.warns(DeprecationWarning, match="build_multimodal_user_message"):
            build_expanded_user_message(parts, "openai-chat")
