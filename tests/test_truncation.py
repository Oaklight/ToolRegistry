"""Unit tests for the truncation module."""

import os

from toolregistry.truncation import (
    TruncatedResult,
    TruncationStrategy,
    truncate_result,
)


class TestTruncatedResult:
    """Test cases for the TruncatedResult dataclass."""

    def test_str_not_truncated(self):
        """Test __str__ for a non-truncated result."""
        tr = TruncatedResult(content="hello", original_size=5, truncated=False)

        assert str(tr) == "hello"

    def test_str_truncated_with_path(self):
        """Test __str__ for a truncated result with a persisted file."""
        tr = TruncatedResult(
            content="hel...",
            original_size=100,
            truncated=True,
            full_path="/tmp/toolregistry_results/test.txt",
        )
        result = str(tr)

        assert "Truncated: 100 chars -> 6 chars" in result
        assert "/tmp/toolregistry_results/test.txt" in result
        assert "hel..." in result

    def test_str_truncated_without_path(self):
        """Test __str__ for a truncated result without persistence."""
        tr = TruncatedResult(
            content="hel...",
            original_size=100,
            truncated=True,
            full_path=None,
        )
        result = str(tr)

        assert "Truncated: 100 chars -> 6 chars" in result
        assert "full output" not in result


class TestTruncateResult:
    """Test cases for the truncate_result function."""

    def test_no_truncation_when_under_limit(self):
        """Test that results under max_size are not truncated."""
        text = "short result"
        tr = truncate_result(text, max_size=100, persist=False)

        assert tr.truncated is False
        assert tr.content == text
        assert tr.original_size == len(text)
        assert tr.full_path is None

    def test_no_truncation_when_at_limit(self):
        """Test that results exactly at max_size are not truncated."""
        text = "x" * 50
        tr = truncate_result(text, max_size=50, persist=False)

        assert tr.truncated is False
        assert tr.content == text

    def test_head_truncation(self):
        """Test head truncation strategy."""
        text = "a" * 200
        tr = truncate_result(
            text, max_size=50, strategy=TruncationStrategy.HEAD, persist=False
        )

        assert tr.truncated is True
        assert len(tr.content) == 50
        assert tr.content == "a" * 50
        assert tr.original_size == 200

    def test_head_tail_truncation(self):
        """Test head+tail truncation strategy with marker."""
        text = "A" * 100 + "B" * 100
        tr = truncate_result(
            text, max_size=80, strategy=TruncationStrategy.HEAD_TAIL, persist=False
        )

        assert tr.truncated is True
        assert tr.original_size == 200
        assert "truncated 120 chars" in tr.content
        assert tr.content.startswith("A")
        assert tr.content.endswith("B")

    def test_head_tail_preserves_head_and_tail(self):
        """Test that head+tail keeps recognizable head and tail portions."""
        head = "HEAD_CONTENT_"
        tail = "_TAIL_CONTENT"
        middle = "x" * 200
        text = head + middle + tail
        tr = truncate_result(
            text, max_size=100, strategy=TruncationStrategy.HEAD_TAIL, persist=False
        )

        assert tr.truncated is True
        assert tr.content.startswith("HEAD_CONTENT_")
        assert tr.content.endswith("_TAIL_CONTENT")

    def test_head_tail_very_small_max_size_falls_back_to_head(self):
        """Test that very small max_size falls back to head truncation."""
        text = "a" * 200
        tr = truncate_result(
            text, max_size=5, strategy=TruncationStrategy.HEAD_TAIL, persist=False
        )

        assert tr.truncated is True
        assert len(tr.content) == 5

    def test_persist_full_result(self):
        """Test that persistence writes the full result to a temp file."""
        text = "x" * 200
        tr = truncate_result(text, max_size=50, tool_name="test_tool", persist=True)

        assert tr.truncated is True
        assert tr.full_path is not None
        assert os.path.exists(tr.full_path)

        with open(tr.full_path, encoding="utf-8") as f:
            persisted = f.read()
        assert persisted == text

        # Cleanup
        os.remove(tr.full_path)

    def test_no_persist(self):
        """Test that persist=False skips file writing."""
        text = "x" * 200
        tr = truncate_result(text, max_size=50, persist=False)

        assert tr.truncated is True
        assert tr.full_path is None

    def test_default_strategy_is_head_tail(self):
        """Test that the default strategy is HEAD_TAIL."""
        text = "A" * 100 + "B" * 100
        tr = truncate_result(text, max_size=80, persist=False)

        # HEAD_TAIL produces a marker in the middle
        assert "truncated" in tr.content
        assert tr.content.startswith("A")
        assert tr.content.endswith("B")
