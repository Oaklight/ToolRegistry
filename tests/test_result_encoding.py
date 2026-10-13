"""Regression tests for tool result JSON encoding (#279).

A tool returning a value that is not JSON-native (a dataclass, a Pydantic
model, an enum, ...) must reach the wire as parseable JSON instead of a
Python ``repr`` string.  Values with no JSON projection must fail loudly
instead of silently degrading to unusable text.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel

from toolregistry import Tool, ToolRegistry
from toolregistry.llm.tool_calls import ErrorResult, ToolCallResult
from toolregistry.tool import ToolMetadata


@dataclass
class SearchResult:
    """Mirrors the dataclass from the issue report."""

    title: str
    url: str
    content: str
    score: float


@dataclass
class Wrapper:
    """A dataclass nested inside another dataclass."""

    inner: SearchResult
    count: int = 0


class Color(Enum):
    RED = "red"
    BLUE = "blue"


class Item(BaseModel):
    """Pydantic v2 model."""

    name: str
    tags: list[str] = []


class Dictable:
    """Exposes the codebase's ``to_dict()`` convention."""

    def to_dict(self) -> dict:
        return {"kind": "dictable", "value": 1}


class Unencodable:
    """Has no JSON projection at all."""

    def __init__(self) -> None:
        self.payload = object()


def _invoke_result(reg: ToolRegistry, name: str, kwargs: dict | None = None) -> str:
    """Invoke *name*, assert success, and return the raw result string."""
    result = reg.invoke(name, kwargs or {})
    assert isinstance(result, ToolCallResult), result
    return result.result


class TestEncodesJSONNative:
    """Values with a JSON projection round-trip through ``json.loads``."""

    def test_list_of_dataclasses(self):
        reg = ToolRegistry()

        def search(q: str) -> list[SearchResult]:
            """Return search hits."""
            return [
                SearchResult(
                    "Title", "http://example.com", "line1\nline2 with 'quotes'", 0.9
                )
            ]

        reg.register(search)
        parsed = json.loads(_invoke_result(reg, "search", {"q": "x"}))

        assert parsed == [
            {
                "title": "Title",
                "url": "http://example.com",
                "content": "line1\nline2 with 'quotes'",
                "score": 0.9,
            }
        ]
        # Not a Python repr string.
        assert "SearchResult(" not in _invoke_result(reg, "search", {"q": "x"})

    def test_nested_dataclass(self):
        reg = ToolRegistry()

        def wrap() -> Wrapper:
            """Return a nested dataclass."""
            return Wrapper(inner=SearchResult("T", "u", "c", 1.0), count=2)

        reg.register(wrap)
        parsed = json.loads(_invoke_result(reg, "wrap"))

        assert parsed["count"] == 2
        assert parsed["inner"]["title"] == "T"
        assert parsed["inner"]["score"] == 1.0

    def test_pydantic_model(self):
        reg = ToolRegistry()

        def make() -> Item:
            """Return a Pydantic model."""
            return Item(name="a", tags=["x", "y"])

        reg.register(make)
        parsed = json.loads(_invoke_result(reg, "make"))

        assert parsed == {"name": "a", "tags": ["x", "y"]}

    def test_enum_uses_value(self):
        reg = ToolRegistry()

        def color() -> dict:
            """Return an enum inside a dict."""
            return {"color": Color.RED}

        reg.register(color)
        assert json.loads(_invoke_result(reg, "color")) == {"color": "red"}

    def test_path_to_string(self):
        reg = ToolRegistry()

        def where() -> dict:
            """Return a path."""
            return {"path": Path("/tmp/data.txt")}

        reg.register(where)
        assert json.loads(_invoke_result(reg, "where")) == {"path": "/tmp/data.txt"}

    def test_set_and_frozenset_and_tuple_to_arrays(self):
        reg = ToolRegistry()

        def collections() -> dict:
            """Return set-like collections."""
            return {"s": {"b", "a"}, "f": frozenset({1}), "t": (1, 2)}

        reg.register(collections)
        parsed = json.loads(_invoke_result(reg, "collections"))

        assert sorted(parsed["s"]) == ["a", "b"]
        assert parsed["f"] == [1]
        assert parsed["t"] == [1, 2]

    def test_scalar_projections(self):
        reg = ToolRegistry()

        def scalars() -> dict:
            """Return assorted scalar types."""
            return {
                "when": datetime(2024, 1, 2, 3, 4, 5),
                "day": date(2024, 1, 2),
                "dec": Decimal("1.50"),
                "uid": uuid.UUID(int=0),
                "blob": b"\x00\x01",
            }

        reg.register(scalars)
        parsed = json.loads(_invoke_result(reg, "scalars"))

        assert parsed["when"] == "2024-01-02T03:04:05"
        assert parsed["day"] == "2024-01-02"
        assert parsed["dec"] == "1.50"
        assert parsed["uid"] == str(uuid.UUID(int=0))
        assert parsed["blob"] == "AAE="

    def test_to_dict_object(self):
        reg = ToolRegistry()

        def make() -> dict:
            """Return an object following the to_dict convention."""
            return {"obj": Dictable()}

        reg.register(make)
        assert json.loads(_invoke_result(reg, "make")) == {
            "obj": {"kind": "dictable", "value": 1}
        }

    def test_quote_and_newline_survive_roundtrip(self):
        reg = ToolRegistry()

        def snippets() -> list[str]:
            """Return strings with quoting hazards."""
            return ["a \"double\" and 'single' and a\nnewline"]

        reg.register(snippets)
        parsed = json.loads(_invoke_result(reg, "snippets"))

        assert parsed == ["a \"double\" and 'single' and a\nnewline"]


class TestPreservedBehaviour:
    """Behaviours that must not regress."""

    def test_plain_str_passthrough(self):
        reg = ToolRegistry()

        def text() -> str:
            """Return plain text."""
            return "hello world"

        reg.register(text)
        assert _invoke_result(reg, "text") == "hello world"

    def test_plain_dict_unchanged(self):
        reg = ToolRegistry()
        assert reg._finalize_result({"key": "value"}, "t") == '{"key": "value"}'

    def test_content_block_list_preserved(self):
        reg = ToolRegistry()
        blocks = [{"type": "text", "text": "hi"}]
        assert reg._finalize_result(blocks, "t") == blocks

    def test_max_result_size_truncates_encoded_result(self):
        reg = ToolRegistry()

        def big() -> list[SearchResult]:
            """Return a large encoded result."""
            return [SearchResult("T", "u", "x" * 400, 1.0)]

        reg.register(Tool.from_function(big, metadata=ToolMetadata(max_result_size=50)))
        raw = _invoke_result(reg, "big")

        assert "Truncated" in raw
        assert len(raw) < 400


class TestUnencodableRaises:
    """Values without a JSON projection fail loudly."""

    def test_finalize_raises_naming_tool_and_type(self):
        reg = ToolRegistry()

        with pytest.raises(TypeError) as excinfo:
            reg._finalize_result(Unencodable(), "bad_tool")

        message = str(excinfo.value)
        assert "bad_tool" in message
        assert "Unencodable" in message

    def test_invoke_surfaces_error_result(self):
        reg = ToolRegistry()

        def bad() -> Unencodable:
            """Return an unencodable object."""
            return Unencodable()

        reg.register(bad)
        result = reg.invoke("bad", {})

        assert isinstance(result, ErrorResult)
        assert "bad" in result.message
        assert "Unencodable" in result.message
