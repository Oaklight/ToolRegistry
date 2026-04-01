"""Tests for multimodal content block support."""

import base64

import pytest

from toolregistry import ToolRegistry
from toolregistry.tool import Tool, ToolMetadata
from toolregistry.types.content_blocks import (
    ContentBlock,
    build_expanded_user_message,
    content_blocks_to_text,
    expand_content_blocks,
    is_content_block_list,
)
from toolregistry.types import (
    build_tool_response,
)
from toolregistry.types.openai.chat_completion import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_IMAGE_DATA = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16).decode()


def _make_text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _make_image_block(
    media_type: str = "image/png", data: str = SAMPLE_IMAGE_DATA
) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def _make_multimodal_blocks() -> list[ContentBlock]:
    return [
        _make_text_block("Here is an image:"),
        _make_image_block(),
    ]


# ---------------------------------------------------------------------------
# is_content_block_list
# ---------------------------------------------------------------------------


class TestIsContentBlockList:
    """Tests for is_content_block_list()."""

    def test_valid_text_only(self):
        assert is_content_block_list([_make_text_block("hello")])

    def test_valid_image_only(self):
        assert is_content_block_list([_make_image_block()])

    def test_valid_mixed(self):
        assert is_content_block_list(_make_multimodal_blocks())

    def test_rejects_empty_list(self):
        assert not is_content_block_list([])

    def test_rejects_plain_string(self):
        assert not is_content_block_list("hello")

    def test_rejects_dict(self):
        assert not is_content_block_list({"type": "text", "text": "hello"})

    def test_rejects_list_of_strings(self):
        assert not is_content_block_list(["hello", "world"])

    def test_rejects_list_with_unknown_type(self):
        assert not is_content_block_list([{"type": "video", "url": "x"}])

    def test_rejects_list_without_type(self):
        assert not is_content_block_list([{"text": "hello"}])

    def test_rejects_mixed_valid_and_invalid(self):
        assert not is_content_block_list(
            [_make_text_block("ok"), {"type": "audio", "data": "x"}]
        )


# ---------------------------------------------------------------------------
# content_blocks_to_text
# ---------------------------------------------------------------------------


class TestContentBlocksToText:
    """Tests for content_blocks_to_text()."""

    def test_text_only(self):
        blocks = [_make_text_block("hello"), _make_text_block("world")]
        assert content_blocks_to_text(blocks) == "hello\nworld"

    def test_image_placeholder(self):
        blocks = [_make_image_block()]
        result = content_blocks_to_text(blocks)
        assert result.startswith("[Image: image/png,")
        assert "bytes]" in result

    def test_mixed_content(self):
        blocks = _make_multimodal_blocks()
        result = content_blocks_to_text(blocks)
        lines = result.split("\n")
        assert lines[0] == "Here is an image:"
        assert lines[1].startswith("[Image:")

    def test_empty_list(self):
        assert content_blocks_to_text([]) == ""


# ---------------------------------------------------------------------------
# expand_content_blocks
# ---------------------------------------------------------------------------


class TestExpandContentBlocks:
    """Tests for expand_content_blocks()."""

    def test_multimodal_response_gets_placeholder(self):
        responses = {"call_1": _make_multimodal_blocks()}
        text_only, extra = expand_content_blocks(responses)

        assert isinstance(text_only["call_1"], str)
        assert '<tool-content call-id="call_1">' in text_only["call_1"]
        assert "See" in text_only["call_1"]

    def test_string_response_passes_through(self):
        responses = {"call_1": "plain text"}
        text_only, extra = expand_content_blocks(responses)

        assert text_only["call_1"] == "plain text"
        assert extra == []

    def test_extra_content_has_xml_tags(self):
        responses = {"call_1": _make_multimodal_blocks()}
        _, extra = expand_content_blocks(responses)

        # Opening tag
        assert extra[0]["type"] == "text"
        assert '<tool-content call-id="call_1">' in extra[0]["text"]
        # Closing tag
        assert extra[-1]["type"] == "text"
        assert "</tool-content>" in extra[-1]["text"]

    def test_extra_content_contains_blocks(self):
        blocks = _make_multimodal_blocks()
        responses = {"call_1": blocks}
        _, extra = expand_content_blocks(responses)

        # Between open/close tags: text block + image block
        assert extra[1]["type"] == "text"
        assert extra[1]["text"] == "Here is an image:"
        assert extra[2]["type"] == "image"

    def test_mixed_responses(self):
        responses = {
            "call_1": "plain text",
            "call_2": _make_multimodal_blocks(),
            "call_3": "more text",
        }
        text_only, extra = expand_content_blocks(responses)

        assert text_only["call_1"] == "plain text"
        assert text_only["call_3"] == "more text"
        assert '<tool-content call-id="call_2">' in text_only["call_2"]
        assert len(extra) > 0

    def test_empty_responses(self):
        text_only, extra = expand_content_blocks({})
        assert text_only == {}
        assert extra == []

    def test_non_string_non_list_response(self):
        responses = {"call_1": 42}
        text_only, extra = expand_content_blocks(responses)

        assert text_only["call_1"] == "42"
        assert extra == []

    def test_multiple_multimodal_responses(self):
        responses = {
            "call_1": _make_multimodal_blocks(),
            "call_2": [_make_image_block()],
        }
        text_only, extra = expand_content_blocks(responses)

        assert '<tool-content call-id="call_1">' in text_only["call_1"]
        assert '<tool-content call-id="call_2">' in text_only["call_2"]
        # Both sets of content in extra
        tags = [
            p
            for p in extra
            if p.get("type") == "text" and "tool-content" in p.get("text", "")
        ]
        assert len(tags) == 4  # 2 open + 2 close


# ---------------------------------------------------------------------------
# build_expanded_user_message
# ---------------------------------------------------------------------------


class TestBuildExpandedUserMessage:
    """Tests for build_expanded_user_message()."""

    @pytest.fixture()
    def sample_parts(self) -> list[dict]:
        return [
            {"type": "text", "text": '<tool-content call-id="call_1">'},
            _make_text_block("description"),
            _make_image_block(),
            {"type": "text", "text": "</tool-content>"},
        ]

    def test_openai_chat_format(self, sample_parts):
        msg = build_expanded_user_message(sample_parts, "openai-chat")
        assert msg["role"] == "user"
        content = msg["content"]
        assert isinstance(content, list)
        # Text parts
        text_parts = [p for p in content if p["type"] == "text"]
        assert len(text_parts) == 3
        # Image part converted to image_url
        image_parts = [p for p in content if p["type"] == "image_url"]
        assert len(image_parts) == 1
        assert image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_openai_response_format(self, sample_parts):
        msg = build_expanded_user_message(sample_parts, "openai-response")
        assert msg["role"] == "user"
        # Same format as openai-chat
        image_parts = [p for p in msg["content"] if p["type"] == "image_url"]
        assert len(image_parts) == 1

    def test_anthropic_format(self, sample_parts):
        msg = build_expanded_user_message(sample_parts, "anthropic")
        assert msg["role"] == "user"
        # Anthropic uses canonical format directly
        assert msg["content"] is sample_parts

    def test_gemini_format(self, sample_parts):
        msg = build_expanded_user_message(sample_parts, "gemini")
        assert msg["role"] == "user"
        parts = msg["parts"]
        text_parts = [p for p in parts if "text" in p]
        assert len(text_parts) == 3
        image_parts = [p for p in parts if "inline_data" in p]
        assert len(image_parts) == 1
        assert image_parts[0]["inline_data"]["mime_type"] == "image/png"

    def test_unknown_format_text_fallback(self, sample_parts):
        msg = build_expanded_user_message(sample_parts, "unknown-api")
        assert msg["role"] == "user"
        assert isinstance(msg["content"], str)


# ---------------------------------------------------------------------------
# _finalize_result with multimodal content
# ---------------------------------------------------------------------------


class TestFinalizeResultMultimodal:
    """Tests for _finalize_result() handling multimodal content."""

    @pytest.fixture()
    def registry(self):
        return ToolRegistry(name="test")

    def test_preserves_content_block_list(self, registry):
        blocks = _make_multimodal_blocks()
        result = registry._finalize_result(blocks, "test_tool")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "image"

    def test_string_result_unchanged(self, registry):
        result = registry._finalize_result("hello", "test_tool")
        assert result == "hello"

    def test_dict_result_json_serialized(self, registry):
        result = registry._finalize_result({"key": "value"}, "test_tool")
        assert result == '{"key": "value"}'

    def test_truncation_only_affects_text_blocks(self, registry):

        def big_text_tool() -> list:
            """Returns multimodal content."""
            return [
                _make_text_block("A" * 200),
                _make_image_block(),
                _make_text_block("B" * 200),
            ]

        registry.register(
            Tool.from_function(
                big_text_tool,
                metadata=ToolMetadata(max_result_size=100),
            )
        )

        blocks = big_text_tool()
        result = registry._finalize_result(blocks, "big_text_tool")
        assert isinstance(result, list)
        # Image block preserved
        image_blocks = [b for b in result if b["type"] == "image"]
        assert len(image_blocks) == 1
        # Total text truncated to <= 100
        total_text = sum(len(b["text"]) for b in result if b["type"] == "text")
        assert total_text <= 100


# ---------------------------------------------------------------------------
# execute_tool_calls with multimodal results
# ---------------------------------------------------------------------------


class TestExecuteToolCallsMultimodal:
    """Integration tests for multimodal results through execute_tool_calls."""

    def test_multimodal_tool_returns_list(self):
        registry = ToolRegistry(name="test")

        def image_tool(path: str) -> list:
            """Returns an image."""
            return _make_multimodal_blocks()

        registry.register(image_tool)

        tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_1",
                function=Function(name="image_tool", arguments='{"path": "test.png"}'),
            )
        ]

        results = registry.execute_tool_calls(tool_calls, execution_mode="thread")
        assert isinstance(results["call_1"], list)
        assert results["call_1"][0]["type"] == "text"
        assert results["call_1"][1]["type"] == "image"

    def test_string_tool_returns_string(self):
        registry = ToolRegistry(name="test")

        def text_tool(x: int) -> str:
            """Returns text."""
            return f"result: {x}"

        registry.register(text_tool)

        tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_2",
                function=Function(name="text_tool", arguments='{"x": 42}'),
            )
        ]

        results = registry.execute_tool_calls(tool_calls, execution_mode="thread")
        assert isinstance(results["call_2"], str)
        assert results["call_2"] == "result: 42"


# ---------------------------------------------------------------------------
# build_tool_response — all formats now use text fallback
# ---------------------------------------------------------------------------


class TestBuildToolResponseMultimodal:
    """Tests for build_tool_response() — all formats use text fallback."""

    @pytest.fixture()
    def multimodal_responses(self) -> dict[str, list]:
        return {"call_1": _make_multimodal_blocks()}

    def test_anthropic_uses_text_fallback(self, multimodal_responses):
        messages = build_tool_response(multimodal_responses, api_format="anthropic")
        tool_result = messages[0]["content"][0]
        assert tool_result["type"] == "tool_result"
        # Now returns text, not content blocks
        assert isinstance(tool_result["content"], str)
        assert "Here is an image:" in tool_result["content"]
        assert "[Image:" in tool_result["content"]

    def test_openai_chat_uses_text_fallback(self, multimodal_responses):
        messages = build_tool_response(multimodal_responses, api_format="openai-chat")
        content = messages[0]["content"]
        assert isinstance(content, str)
        assert "Here is an image:" in content
        assert "[Image:" in content

    def test_openai_response_uses_text_fallback(self, multimodal_responses):
        messages = build_tool_response(
            multimodal_responses, api_format="openai-response"
        )
        output = messages[0]["output"]
        assert isinstance(output, str)
        assert "Here is an image:" in output

    def test_gemini_uses_text_fallback(self, multimodal_responses):
        from toolregistry.types.common import ToolCall

        tc = ToolCall(id="call_1", name="image_tool", arguments="{}")
        messages = build_tool_response(
            multimodal_responses, api_format="gemini", tool_calls=[tc]
        )
        output = messages[0]["parts"][0]["functionResponse"]["response"]["output"]
        assert isinstance(output, str)
        assert "[Image:" in output

    def test_anthropic_string_result_unchanged(self):
        responses = {"call_1": "plain text result"}
        messages = build_tool_response(responses, api_format="anthropic")
        tool_result = messages[0]["content"][0]
        assert tool_result["content"] == "plain text result"

    def test_openai_string_result_unchanged(self):
        responses = {"call_1": "plain text result"}
        messages = build_tool_response(responses, api_format="openai-chat")
        assert messages[0]["content"] == "plain text result"


# ---------------------------------------------------------------------------
# build_tool_call_messages end-to-end (uniform expansion)
# ---------------------------------------------------------------------------


class TestBuildToolCallMessagesMultimodal:
    """End-to-end tests for uniform multimodal expansion."""

    def _setup_image_tool(self):
        registry = ToolRegistry(name="test")

        def image_tool(path: str) -> list:
            """Returns multimodal content."""
            return _make_multimodal_blocks()

        registry.register(image_tool)

        tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_1",
                function=Function(name="image_tool", arguments='{"path": "test.png"}'),
            )
        ]
        responses = registry.execute_tool_calls(tool_calls, execution_mode="thread")
        return registry, tool_calls, responses

    def test_anthropic_end_to_end(self):
        registry, tool_calls, responses = self._setup_image_tool()
        messages = registry.build_tool_call_messages(
            tool_calls, responses, api_format="anthropic"
        )

        # Should have: assistant msg, tool result msg, expanded user msg
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assert len(user_msgs) == 2  # tool result + expanded content

        # Tool result has placeholder text
        tool_result = user_msgs[0]["content"][0]
        assert isinstance(tool_result["content"], str)
        assert "tool-content" in tool_result["content"]

        # Expanded user message has actual image
        expanded = user_msgs[1]
        image_blocks = [
            p
            for p in expanded["content"]
            if isinstance(p, dict) and p.get("type") == "image"
        ]
        assert len(image_blocks) == 1

    def test_openai_chat_end_to_end(self):
        registry, tool_calls, responses = self._setup_image_tool()
        messages = registry.build_tool_call_messages(
            tool_calls, responses, api_format="openai-chat"
        )

        # Tool result has placeholder
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "tool-content" in tool_msgs[0]["content"]

        # Expanded user message has image_url
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assert len(user_msgs) == 1
        image_parts = [
            p for p in user_msgs[0]["content"] if p.get("type") == "image_url"
        ]
        assert len(image_parts) == 1

    def test_gemini_end_to_end(self):
        registry, tool_calls, responses = self._setup_image_tool()
        messages = registry.build_tool_call_messages(
            tool_calls, responses, api_format="gemini"
        )

        # Expanded user message has inline_data
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assert len(user_msgs) == 2  # tool result + expanded
        expanded = user_msgs[1]
        inline_parts = [p for p in expanded["parts"] if "inline_data" in p]
        assert len(inline_parts) == 1

    def test_no_expansion_for_text_only(self):
        registry = ToolRegistry(name="test")

        def text_tool(x: int) -> str:
            """Returns text."""
            return f"result: {x}"

        registry.register(text_tool)

        tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_1",
                function=Function(name="text_tool", arguments='{"x": 42}'),
            )
        ]
        responses = registry.execute_tool_calls(tool_calls, execution_mode="thread")
        messages = registry.build_tool_call_messages(
            tool_calls, responses, api_format="openai-chat"
        )

        # No expanded user message for text-only results
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assert len(user_msgs) == 0
