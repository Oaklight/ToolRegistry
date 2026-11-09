"""Content-aware truncation and the token budget (#418 L2/L3)."""

import json

import pytest

from toolregistry import Tool, ToolRegistry, ToolMetadata
from toolregistry.llm.truncation import (
    CHARS_PER_TOKEN,
    TruncationStrategy,
    truncate_result,
)


class TestTokenBudget:
    def test_chars_per_token_is_the_documented_estimate(self):
        assert CHARS_PER_TOKEN == 4

    def test_registry_default_tokens_convert_to_characters(self):
        registry = ToolRegistry(default_max_result_tokens=10)
        assert registry._result_char_budget("missing") == 40

    def test_the_smaller_limit_wins(self):
        assert (
            ToolRegistry(
                default_max_result_size=30, default_max_result_tokens=10
            )._result_char_budget("missing")
            == 30
        )
        assert (
            ToolRegistry(
                default_max_result_size=100, default_max_result_tokens=10
            )._result_char_budget("missing")
            == 40
        )

    def test_tool_level_tokens_override_the_registry_default(self):
        registry = ToolRegistry(
            default_max_result_size=1000, default_max_result_tokens=10
        )

        def small() -> str:
            """Return a value."""
            return "x"

        registry.register(
            Tool.from_function(small, metadata=ToolMetadata(max_result_tokens=5))
        )
        assert registry._result_char_budget("small") == 20

    def test_char_only_configuration_is_unchanged(self):
        registry = ToolRegistry(default_max_result_size=40)
        assert registry._result_char_budget("missing") == 40

    def test_negative_and_non_integer_limits_are_refused(self):
        for value in (-1, True, 1.5, "10"):
            with pytest.raises(ValueError, match="max_result_tokens"):
                ToolMetadata(max_result_tokens=value)

    def test_zero_and_none_are_allowed(self):
        assert ToolMetadata(max_result_tokens=0).max_result_tokens == 0
        assert ToolMetadata().max_result_tokens is None

    def test_the_field_is_appended_last(self):
        metadata = ToolMetadata(
            False,
            True,
            None,
            "any",
            None,
            set(),
            set(),
            "native",
            "",
            "",
            "",
            {},
            True,
            "hint",
            False,
            None,
            "Title",
            None,
            None,
            None,
            None,
        )
        assert metadata.defer is True
        assert metadata.search_hint == "hint"
        assert metadata.title == "Title"
        assert metadata.max_result_tokens is None


class TestResultSizeValidation:
    def test_negative_and_non_integer_caps_are_refused(self):
        for value in (-1, True, 1.5, "10"):
            with pytest.raises(ValueError, match="max_result_size"):
                ToolMetadata(max_result_size=value)

    def test_zero_and_none_caps_are_allowed(self):
        assert ToolMetadata(max_result_size=0).max_result_size == 0
        assert ToolMetadata().max_result_size is None

    def test_registry_refuses_an_invalid_default_cap(self):
        for value in (-1, True, 1.5, "10"):
            with pytest.raises(ValueError, match="default_max_result_size"):
                ToolRegistry(default_max_result_size=value)

    def test_registry_refuses_an_invalid_default_token_budget(self):
        for value in (-1, True, 1.5, "10"):
            with pytest.raises(ValueError, match="default_max_result_tokens"):
                ToolRegistry(default_max_result_tokens=value)

    def test_registry_allows_zero_and_none_caps(self):
        assert ToolRegistry(default_max_result_size=0)._result_char_budget("x") == 0
        assert ToolRegistry()._result_char_budget("x") is None
        assert ToolRegistry(default_max_result_tokens=0)._result_char_budget("x") == 0


class TestJsonAwareTruncation:
    def test_a_dict_root_gains_a_truncation_key_with_counts(self):
        text = json.dumps({f"k{index}": index for index in range(10)})

        tr = truncate_result(text, max_size=60, persist=False)

        data = json.loads(tr.content)
        assert set(data) == {"_truncation"}
        assert data["_truncation"] == {
            "omitted_items": 10,
            "omitted_chars": 60,
        }

    def test_a_list_root_gains_one_sentinel_and_keeps_parsing(self):
        text = json.dumps(list(range(30)))

        tr = truncate_result(text, max_size=60, persist=False)

        data = json.loads(tr.content)
        assert len(data) >= 2
        assert data[0] == 0
        assert data[-1]["_truncation"]["omitted_items"] > 0
        assert data[-1]["_truncation"]["omitted_chars"] > 0
        assert len(tr.content) <= 60

    def test_an_existing_truncation_key_is_not_overwritten(self):
        text = json.dumps({"_truncation": "operator data", "x": "y" * 500})

        tr = truncate_result(text, max_size=120, persist=False)

        data = json.loads(tr.content)
        assert data["_truncation"] == "operator data"
        assert "_truncation_1" in data
        assert data["_truncation_1"]["omitted_chars"] > 0

    def test_over_long_strings_carry_their_own_count(self):
        text = json.dumps({"s": "x" * 1000})

        tr = truncate_result(text, max_size=200, persist=False)

        data = json.loads(tr.content)
        assert data["_truncation"]["omitted_items"] == 0
        assert data["_truncation"]["omitted_chars"] > 0
        assert "chars]" in data["s"]

    def test_a_json_scalar_root_stays_valid(self):
        text = json.dumps("y" * 200)

        tr = truncate_result(text, max_size=50, persist=False)

        assert isinstance(json.loads(tr.content), str)
        assert len(tr.content) <= 50

    def test_json_output_parses_when_it_fits_the_budget(self):
        text = json.dumps({"items": [{"value": index} for index in range(200)]})
        for budget in (60, 100, 500, 2000):
            tr = truncate_result(text, max_size=budget, persist=False)
            data = json.loads(tr.content)
            assert len(tr.content) <= budget
            assert isinstance(data, dict)

    def test_metadata_that_cannot_fit_falls_back_to_text(self):
        text = json.dumps({"a": "x" * 100, "b": 1})

        tr = truncate_result(text, max_size=20, persist=False)

        # The omission metadata alone is longer than the budget, so the
        # document is text-truncated and no longer parses.
        assert len(tr.content) <= 20
        assert tr.content == text[:20]
        with pytest.raises(json.JSONDecodeError):
            json.loads(tr.content)

    def test_deeply_nested_json_falls_back_to_text_without_raising(self):
        text = "[" * 2000 + "]" * 2000

        tr = truncate_result(text, max_size=80, persist=False)

        assert tr.truncated is True
        assert len(tr.content) <= 80


class TestTextTruncation:
    def test_it_splits_on_line_boundaries(self):
        text = "".join(f"line {index}\n" for index in range(15))

        tr = truncate_result(text, max_size=80, persist=False)

        assert tr.content.startswith("line 0\n")
        assert tr.content.endswith("line 14\n")
        assert "(11 lines, 80 chars omitted)" in tr.content

    def test_text_without_line_structure_keeps_the_char_split(self):
        text = "A" * 100 + "B" * 100

        tr = truncate_result(
            text, max_size=80, strategy=TruncationStrategy.HEAD_TAIL, persist=False
        )

        assert "truncated 120 chars" in tr.content
        assert tr.content.startswith("A")
        assert tr.content.endswith("B")

    def test_invalid_json_falls_back_and_does_not_raise(self):
        text = '{\n"a": 1,\n"b": '

        tr = truncate_result(text, max_size=10, persist=False)

        assert tr.truncated is True
        assert tr.content == text[:10]


class TestContentBlocks:
    def test_text_blocks_share_the_budget_proportionally(self):
        registry = ToolRegistry()
        image = {"type": "image", "source": {"type": "base64", "data": "abc"}}
        blocks = [
            {"type": "text", "text": "A" * 300},
            image,
            {"type": "text", "text": "B" * 100},
            {"type": "text", "text": "C" * 100},
        ]

        result = registry._truncate_content_blocks(blocks, 100, "tool")

        texts = [len(block["text"]) for block in result if block["type"] == "text"]
        assert sum(texts) <= 100
        assert texts[0] > texts[1]
        assert texts[0] > texts[2]
        assert any(block["type"] == "image" for block in result)


class TestExecutePath:
    def test_a_token_budget_truncates_and_keeps_the_payload_json(self):
        registry = ToolRegistry(default_max_result_tokens=25)

        def data_tool() -> dict:
            """Return many records."""
            return {"items": [{"value": index} for index in range(200)]}

        registry.register(data_tool)
        results = registry.execute_tool_calls(
            [
                {
                    "id": "call_data",
                    "type": "function",
                    "function": {"name": "data_tool", "arguments": "{}"},
                }
            ]
        )

        raw = results["call_data"].result
        assert "Truncated" in raw
        payload = raw.split("\n", 1)[1]
        parsed = json.loads(payload)
        assert parsed["_truncation"]["omitted_items"] >= 1
