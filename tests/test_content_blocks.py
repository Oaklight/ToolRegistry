"""Tests for multimodal content block support."""

import base64

import pytest

from toolregistry import ToolRegistry
from toolregistry.tool import Tool, ToolMetadata
from toolregistry.types.content_blocks import (
    ContentBlock,
    content_blocks_to_text,
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
# build_tool_response with multimodal results
# ---------------------------------------------------------------------------


class TestBuildToolResponseMultimodal:
    """Tests for build_tool_response() multimodal dispatch per API format."""

    @pytest.fixture()
    def multimodal_responses(self) -> dict[str, list]:
        return {"call_1": _make_multimodal_blocks()}

    def test_anthropic_passes_through_content_blocks(self, multimodal_responses):
        messages = build_tool_response(multimodal_responses, api_format="anthropic")
        assert len(messages) == 1
        tool_result = messages[0]["content"][0]
        assert tool_result["type"] == "tool_result"
        # Content should be the list of content blocks, not a string
        assert isinstance(tool_result["content"], list)
        assert tool_result["content"][0]["type"] == "text"
        assert tool_result["content"][1]["type"] == "image"

    def test_openai_chat_falls_back_to_text(self, multimodal_responses):
        messages = build_tool_response(multimodal_responses, api_format="openai-chat")
        content = messages[0]["content"]
        assert isinstance(content, str)
        assert "Here is an image:" in content
        assert "[Image:" in content

    def test_openai_response_falls_back_to_text(self, multimodal_responses):
        messages = build_tool_response(
            multimodal_responses, api_format="openai-response"
        )
        output = messages[0]["output"]
        assert isinstance(output, str)
        assert "Here is an image:" in output

    def test_gemini_falls_back_to_text(self, multimodal_responses):
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
# build_tool_call_messages end-to-end
# ---------------------------------------------------------------------------


class TestBuildToolCallMessagesMultimodal:
    """End-to-end test for multimodal results through build_tool_call_messages."""

    def test_anthropic_end_to_end(self):
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
        messages = registry.build_tool_call_messages(
            tool_calls, responses, api_format="anthropic"
        )

        # Find the tool result message
        tool_result_msg = [m for m in messages if m.get("role") == "user"]
        assert len(tool_result_msg) == 1
        tool_result = tool_result_msg[0]["content"][0]
        assert isinstance(tool_result["content"], list)
        assert tool_result["content"][0]["type"] == "text"
        assert tool_result["content"][1]["type"] == "image"
