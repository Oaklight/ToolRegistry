"""Tests for Anthropic, Gemini, and rosetta-based OpenAI schema format support.

Covers get_json_schema(), ToolCall.from_tool_call(),
recover_assistant_message(), and recover_tool_message().
"""

import json


from toolregistry import Tool
from toolregistry.types.common import (
    ToolCall,
    recover_assistant_message,
    recover_tool_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_tool() -> Tool:
    """Create a sample tool for testing."""

    def add(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b

    return Tool.from_function(add)


# ---------------------------------------------------------------------------
# get_json_schema — Anthropic
# ---------------------------------------------------------------------------


class TestGetJsonSchemaAnthropic:
    def test_returns_input_schema_key(self):
        tool = _sample_tool()
        schema = tool.get_json_schema(api_format="anthropic")
        assert "input_schema" in schema
        assert "parameters" not in schema

    def test_has_name_and_description(self):
        tool = _sample_tool()
        schema = tool.get_json_schema(api_format="anthropic")
        assert schema["name"] == "add"
        assert "Add two numbers" in schema["description"]

    def test_input_schema_is_valid_json_schema(self):
        tool = _sample_tool()
        schema = tool.get_json_schema(api_format="anthropic")
        input_schema = schema["input_schema"]
        assert input_schema["type"] == "object"
        assert "properties" in input_schema

    def test_no_type_wrapper(self):
        tool = _sample_tool()
        schema = tool.get_json_schema(api_format="anthropic")
        # Anthropic format is flat — no "type": "function" wrapper
        assert "type" not in schema or schema.get("type") != "function"


# ---------------------------------------------------------------------------
# get_json_schema — Gemini
# ---------------------------------------------------------------------------


class TestGetJsonSchemaGemini:
    def test_returns_flat_format(self):
        tool = _sample_tool()
        schema = tool.get_json_schema(api_format="gemini")
        # Should be unwrapped (no function_declarations wrapper)
        assert "function_declarations" not in schema
        assert "name" in schema
        assert "parameters" in schema

    def test_has_name_and_description(self):
        tool = _sample_tool()
        schema = tool.get_json_schema(api_format="gemini")
        assert schema["name"] == "add"
        assert "Add two numbers" in schema["description"]

    def test_parameters_is_valid_json_schema(self):
        tool = _sample_tool()
        schema = tool.get_json_schema(api_format="gemini")
        params = schema["parameters"]
        assert params["type"] == "object"
        assert "properties" in params


# ---------------------------------------------------------------------------
# get_json_schema — Rosetta vs Native OpenAI comparison
# ---------------------------------------------------------------------------


class TestGetJsonSchemaOpenAI:
    """Verify OpenAI formats via rosetta produce correct structure."""

    def test_openai_chat_format(self):
        tool = _sample_tool()
        schema = tool.get_json_schema(api_format="openai")
        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "add"
        assert "Add two numbers" in schema["function"]["description"]
        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        assert "a" in params["properties"]
        assert "b" in params["properties"]

    def test_openai_response_format(self):
        tool = _sample_tool()
        schema = tool.get_json_schema(api_format="openai-response")
        assert schema["type"] == "function"
        assert schema["name"] == "add"
        assert "Add two numbers" in schema["description"]
        assert schema["strict"] is False
        params = schema["parameters"]
        assert params["type"] == "object"
        assert "a" in params["properties"]

    def test_schema_sanitization_strips_unsupported_keywords(self):
        """Rosetta sanitizes schemas (removes $ref, $schema, etc)."""
        from toolregistry._rosetta import (
            _get_anthropic_tool_ops,
            _make_ir_tool_definition,
        )

        ir_tool = _make_ir_tool_definition(
            "test",
            "test tool",
            {
                "type": "object",
                "$schema": "http://json-schema.org/draft-07/schema#",
                "properties": {"x": {"type": "string"}},
            },
        )
        ops = _get_anthropic_tool_ops()
        result = ops.ir_tool_definition_to_p(ir_tool)
        assert "$schema" not in result["input_schema"]


# ---------------------------------------------------------------------------
# ToolCall.from_tool_call — Anthropic
# ---------------------------------------------------------------------------


class TestFromToolCallAnthropic:
    def test_tool_use_block(self):
        tc = ToolCall.from_tool_call(
            {
                "type": "tool_use",
                "id": "toolu_abc123",
                "name": "add",
                "input": {"a": 1, "b": 2},
            }
        )
        assert tc.id == "toolu_abc123"
        assert tc.name == "add"
        assert json.loads(tc.arguments) == {"a": 1, "b": 2}
        assert tc.type == "function"

    def test_server_tool_use_block(self):
        tc = ToolCall.from_tool_call(
            {
                "type": "server_tool_use",
                "id": "toolu_srv456",
                "name": "web_search",
                "input": {"query": "hello"},
            }
        )
        assert tc.id == "toolu_srv456"
        assert tc.name == "web_search"
        assert tc.type == "function"

    def test_empty_input(self):
        tc = ToolCall.from_tool_call(
            {
                "type": "tool_use",
                "id": "toolu_empty",
                "name": "noop",
                "input": {},
            }
        )
        assert json.loads(tc.arguments) == {}


# ---------------------------------------------------------------------------
# ToolCall.from_tool_call — Gemini
# ---------------------------------------------------------------------------


class TestFromToolCallGemini:
    def test_function_call_camel_case(self):
        tc = ToolCall.from_tool_call(
            {
                "functionCall": {
                    "name": "add",
                    "args": {"a": 1, "b": 2},
                }
            }
        )
        assert tc.name == "add"
        assert json.loads(tc.arguments) == {"a": 1, "b": 2}
        assert tc.type == "function"
        # ID should be auto-generated (non-empty)
        assert len(tc.id) > 0

    def test_function_call_snake_case(self):
        tc = ToolCall.from_tool_call(
            {
                "function_call": {
                    "name": "subtract",
                    "args": {"a": 5, "b": 3},
                }
            }
        )
        assert tc.name == "subtract"
        assert json.loads(tc.arguments) == {"a": 5, "b": 3}

    def test_function_call_with_id(self):
        tc = ToolCall.from_tool_call(
            {
                "functionCall": {
                    "id": "fc_custom_id",
                    "name": "add",
                    "args": {},
                }
            }
        )
        assert tc.id == "fc_custom_id"


# ---------------------------------------------------------------------------
# recover_assistant_message — Anthropic
# ---------------------------------------------------------------------------


class TestRecoverAssistantMessageAnthropic:
    def test_basic_structure(self):
        tool_calls = [
            ToolCall(
                id="toolu_1",
                name="add",
                arguments=json.dumps({"a": 1, "b": 2}),
            )
        ]
        result = recover_assistant_message(tool_calls, api_format="anthropic")
        assert len(result) == 1
        msg = result[0]
        assert msg["role"] == "assistant"
        assert len(msg["content"]) == 1
        block = msg["content"][0]
        assert block["type"] == "tool_use"
        assert block["id"] == "toolu_1"
        assert block["name"] == "add"
        assert block["input"] == {"a": 1, "b": 2}

    def test_multiple_tool_calls(self):
        tool_calls = [
            ToolCall(id="t1", name="add", arguments=json.dumps({"a": 1, "b": 2})),
            ToolCall(id="t2", name="sub", arguments=json.dumps({"x": 5})),
        ]
        result = recover_assistant_message(tool_calls, api_format="anthropic")
        assert len(result) == 1
        assert len(result[0]["content"]) == 2

    def test_skips_empty_tool_calls(self):
        tool_calls = [
            ToolCall(id="t1", name="", arguments="{}"),
        ]
        result = recover_assistant_message(tool_calls, api_format="anthropic")
        assert result[0]["content"] == []


# ---------------------------------------------------------------------------
# recover_assistant_message — Gemini
# ---------------------------------------------------------------------------


class TestRecoverAssistantMessageGemini:
    def test_basic_structure(self):
        tool_calls = [
            ToolCall(
                id="fc_1",
                name="add",
                arguments=json.dumps({"a": 1, "b": 2}),
            )
        ]
        result = recover_assistant_message(tool_calls, api_format="gemini")
        assert len(result) == 1
        msg = result[0]
        assert msg["role"] == "model"
        assert len(msg["parts"]) == 1
        part = msg["parts"][0]
        assert "functionCall" in part
        assert part["functionCall"]["name"] == "add"
        assert part["functionCall"]["args"] == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# recover_tool_message — Anthropic
# ---------------------------------------------------------------------------


class TestRecoverToolMessageAnthropic:
    def test_basic_structure(self):
        responses = {"toolu_1": "3"}
        result = recover_tool_message(responses, api_format="anthropic")
        assert len(result) == 1
        msg = result[0]
        assert msg["role"] == "user"
        assert len(msg["content"]) == 1
        block = msg["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "toolu_1"
        assert block["content"] == "3"

    def test_multiple_results(self):
        responses = {"t1": "result1", "t2": "result2"}
        result = recover_tool_message(responses, api_format="anthropic")
        assert len(result) == 1
        assert len(result[0]["content"]) == 2


# ---------------------------------------------------------------------------
# recover_tool_message — Gemini
# ---------------------------------------------------------------------------


class TestRecoverToolMessageGemini:
    def test_basic_structure(self):
        responses = {"fc_1": "42"}
        tcs = [ToolCall(id="fc_1", name="add", arguments="{}")]
        result = recover_tool_message(responses, api_format="gemini", tool_calls=tcs)
        assert len(result) == 1
        msg = result[0]
        assert msg["role"] == "user"
        assert len(msg["parts"]) == 1
        part = msg["parts"][0]
        assert "functionResponse" in part
        assert part["functionResponse"]["name"] == "add"
        assert part["functionResponse"]["response"]["output"] == "42"

    def test_fallback_to_call_id_when_no_tool_calls(self):
        responses = {"fc_1": "42"}
        result = recover_tool_message(responses, api_format="gemini")
        # Without tool_calls, falls back to call_id as function name
        part = result[0]["parts"][0]
        assert part["functionResponse"]["name"] == "fc_1"


# ---------------------------------------------------------------------------
# Round-trip: from_tool_call -> recover_assistant_message
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_anthropic_round_trip(self):
        """Parse Anthropic tool call, then recover it back."""
        original = {
            "type": "tool_use",
            "id": "toolu_rt1",
            "name": "add",
            "input": {"a": 10, "b": 20},
        }
        tc = ToolCall.from_tool_call(original)
        recovered = recover_assistant_message([tc], api_format="anthropic")
        block = recovered[0]["content"][0]
        assert block["type"] == original["type"]
        assert block["id"] == original["id"]
        assert block["name"] == original["name"]
        assert block["input"] == original["input"]

    def test_gemini_round_trip(self):
        """Parse Gemini tool call, then recover it back."""
        original = {
            "functionCall": {
                "name": "multiply",
                "args": {"x": 3, "y": 7},
            }
        }
        tc = ToolCall.from_tool_call(original)
        recovered = recover_assistant_message([tc], api_format="gemini")
        part = recovered[0]["parts"][0]
        assert part["functionCall"]["name"] == original["functionCall"]["name"]
        assert part["functionCall"]["args"] == original["functionCall"]["args"]
