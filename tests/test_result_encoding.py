"""Regression tests for tool result JSON encoding (#279).

A tool returning a value that is not JSON-native (a dataclass, a Pydantic
model, an enum, ...) must reach the wire as parseable JSON instead of a
Python ``repr`` string.  Values with no JSON projection must fail loudly
instead of silently degrading to unusable text.
"""

from __future__ import annotations

import enum
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum, IntEnum
from pathlib import Path

import pytest
from pydantic import BaseModel

from toolregistry import Tool, ToolRegistry
from toolregistry.llm.tool_calls import ErrorResult, ToolCallResult
from toolregistry.tool import ToolMetadata
from toolregistry.utils import encode_tool_result

_SRC = str(Path(__file__).resolve().parents[1] / "src")


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


class IntColor(IntEnum):
    """Integer-valued enum; members are also ``int`` instances."""

    ONE = 1


class StrColor(str, Enum):
    """String-valued enum; members are also ``str`` instances.

    This is the pre-3.11 shape of :class:`enum.StrEnum`; a test below also
    exercises the stdlib ``StrEnum`` when the interpreter provides it.
    """

    ALPHA = "alpha"


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


class ArrayLike:
    """Exposes only ``tolist()``, like numpy arrays and torch tensors."""

    def __init__(self, values: list) -> None:
        self._values = values

    def tolist(self) -> list:
        return self._values


@dataclass(frozen=True)
class FrozenPoint:
    """Hashable (so usable in a set) but not orderable."""

    x: int


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

        assert parsed["s"] == ["a", "b"]
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

    def test_error_message_names_the_fix(self):
        reg = ToolRegistry()

        with pytest.raises(TypeError) as excinfo:
            reg._finalize_result(Unencodable(), "bad_tool")

        message = str(excinfo.value)
        assert "to_dict" in message or "model_dump" in message
        assert "str" in message


class TestTopLevelProjection:
    """Top-level projection must agree with the nested one for every type."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (Path("/tmp/x"), "/tmp/x"),
            (Decimal("1.50"), "1.50"),
            (uuid.UUID(int=0), str(uuid.UUID(int=0))),
            (date(2024, 1, 2), "2024-01-02"),
            (time(3, 4, 5), "03:04:05"),
            (Color.RED, "red"),
            (IntColor.ONE, 1),
            (StrColor.ALPHA, "alpha"),
            (datetime(2024, 1, 2, 3, 4, 5), "2024-01-02T03:04:05"),
            (b"\x00\x01", "AAE="),
        ],
    )
    def test_top_level_matches_nested(self, value, expected):
        nested = json.loads(encode_tool_result({"v": value}))["v"]
        top_raw = encode_tool_result(value)
        # Allowlisted scalars are emitted as a bare string; everything
        # else is JSON text, so decode it before comparing content.
        top = top_raw if top_raw == expected else json.loads(top_raw)

        assert top == expected
        assert nested == expected

    def test_plain_str_stays_bare(self):
        assert encode_tool_result("hello") == "hello"

    def test_strenum_is_not_returned_as_member(self):
        # Regression: a str-mixin enum used to slip through the plain-str
        # branch and come back as the member, whose ``str()`` is
        # ``StrColor.ALPHA`` rather than the value.
        assert encode_tool_result(StrColor.ALPHA) == '"alpha"'

    def test_intenum_projects_through_value(self):
        assert json.loads(encode_tool_result(IntColor.ONE)) == 1
        assert json.loads(encode_tool_result({"v": IntColor.ONE})) == {"v": 1}

    def test_stdlib_strenum_matches_when_available(self):
        str_enum = getattr(enum, "StrEnum", None)
        if str_enum is None:
            pytest.skip("enum.StrEnum requires Python 3.11+")

        class Builtin(str_enum):  # type: ignore[misc, valid-type]
            ALPHA = "alpha"

        assert json.loads(encode_tool_result(Builtin.ALPHA)) == "alpha"
        assert json.loads(encode_tool_result({"v": Builtin.ALPHA})) == {"v": "alpha"}


class TestSetDeterminism:
    """Sets encode with a total, reproducible order (``sorted(..., key=repr)``)."""

    def test_orderable_set_is_sorted(self):
        reg = ToolRegistry()

        def tags() -> dict:
            """Return an unordered set."""
            return {"tags": {"delta", "alpha", "charlie", "bravo"}}

        reg.register(tags)
        parsed = json.loads(_invoke_result(reg, "tags"))

        assert parsed["tags"] == ["alpha", "bravo", "charlie", "delta"]

    def test_set_encoding_identical_across_processes(self):
        code = (
            "from toolregistry.utils import encode_tool_result;"
            "print(encode_tool_result({'s': {'delta', 'alpha', 'charlie', 'bravo'},"
            " 'm': {1, 'a', None, 2.5}}))"
        )
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                p for p in (_SRC, os.environ.get("PYTHONPATH", "")) if p
            ),
        }

        def run_once() -> str:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
            return proc.stdout

        first, second = run_once(), run_once()

        assert first == second
        assert '"alpha"' in first

    def test_mixed_type_set_is_repr_sorted(self):
        reg = ToolRegistry()

        def mixed() -> dict:
            """Return a set of mutually non-comparable elements."""
            return {"mixed": {1, "a"}}

        reg.register(mixed)
        parsed = json.loads(_invoke_result(reg, "mixed"))

        # ``repr`` is a total order: "'a'" sorts before "1".
        assert parsed["mixed"] == ["a", 1]

    def test_dataclass_set_is_reproducible(self):
        reg = ToolRegistry()

        def fuzzy() -> dict:
            """Return a set of non-orderable dataclasses."""
            return {"fuzzy": {FrozenPoint(2), FrozenPoint(1)}}

        reg.register(fuzzy)
        parsed = json.loads(_invoke_result(reg, "fuzzy"))

        assert parsed["fuzzy"] == [{"x": 1}, {"x": 2}]


class TestTolistProjection:
    """Array-like objects project through ``tolist()``."""

    def test_tolist_routes_through_encoder(self):
        reg = ToolRegistry()

        def arr() -> dict:
            """Return an array-like object."""
            return {"a": ArrayLike([Decimal("1.5"), datetime(2024, 1, 2, 3, 4, 5)])}

        reg.register(arr)
        parsed = json.loads(_invoke_result(reg, "arr"))

        assert parsed["a"] == ["1.5", "2024-01-02T03:04:05"]

    def test_tolist_non_native_element_raises(self):
        class BadArray:
            """``tolist`` returning a value with no JSON projection."""

            def tolist(self) -> list:
                return [Unencodable()]

        reg = ToolRegistry()

        def arr() -> BadArray:
            """Return an array-like with a non-native element."""
            return BadArray()

        reg.register(arr)
        result = reg.invoke("arr", {})

        assert isinstance(result, ErrorResult)
        assert "arr" in result.message
        assert "Unencodable" in result.message


class TestProcessModeUsesEncoder:
    """The process backend must not stringify before the parent encodes.

    Regression for #288: ``_process_worker`` used to ``str()`` any result
    that failed ``json.dumps``, so on the default ``"process"`` backend the
    parent's encoder -- and its raise policy -- never saw the value.
    """

    def test_process_and_thread_agree_on_dataclass(self):
        reg = ToolRegistry()

        def make() -> SearchResult:
            """Return a dataclass."""
            return SearchResult("T", "u", "c", 1.0)

        reg.register(make)
        try:
            thread = reg.invoke("make", {}, execution_mode="thread")
            process = reg.invoke("make", {}, execution_mode="process")
        finally:
            reg._process_backend.shutdown()

        assert isinstance(thread, ToolCallResult)
        assert isinstance(process, ToolCallResult)
        assert process.result == thread.result
        assert json.loads(process.result)["title"] == "T"
        # Not the worker's old ``str()`` fallback.
        assert "SearchResult(" not in process.result

    def test_process_unencodable_matches_thread(self):
        reg = ToolRegistry()

        def bad() -> Unencodable:
            """Return a value with no JSON projection."""
            return Unencodable()

        reg.register(bad)
        try:
            thread = reg.invoke("bad", {}, execution_mode="thread")
            process = reg.invoke("bad", {}, execution_mode="process")
        finally:
            reg._process_backend.shutdown()

        assert isinstance(thread, ErrorResult)
        assert isinstance(process, ErrorResult)
        assert "Unencodable" in process.message

    def test_process_unpicklable_result_explains_boundary(self):
        """A result that cannot be pickled names the backend, not just pickle.

        Regression for #288: the worker's pickling failure reached the
        caller as a bare ``TypeError``/``AttributeError`` with no hint
        that the process backend was the reason.
        """
        reg = ToolRegistry()

        def gen():
            """Return a generator, which cannot cross a process boundary."""
            return (x for x in (1, 2))

        reg.register(gen, namespace="ns")
        tool_call = [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "ns-gen", "arguments": "{}"},
            }
        ]
        try:
            process = reg.invoke("ns-gen", {}, execution_mode="process")
            thread = reg.invoke("ns-gen", {}, execution_mode="thread")
            batch = reg.execute_tool_calls(tool_call)[0]
        finally:
            reg._process_backend.shutdown()

        assert isinstance(process, ErrorResult)
        assert "UnpicklableResultError" in process.message
        assert "ns-gen" in process.message
        assert "must pickle the tool result" in process.message
        assert "thread backend" in process.message

        # The thread path still reports the encoder's diagnosis.
        assert isinstance(thread, ErrorResult)
        assert "cannot be encoded to JSON" in thread.message

        # The batch default (process) matches invoke(execution_mode="process").
        assert isinstance(batch, ErrorResult)
        assert "UnpicklableResultError" in batch.message
        assert "must pickle the tool result" in batch.message

    def test_process_unpicklable_native_class_method_explains_boundary(self):
        """Native (class-based) tools use the process backend and get the hint."""

        class Native:
            def gen(self):
                """Return a generator."""
                return (x for x in (1, 2))

        reg = ToolRegistry()
        reg.register(Native, source="class", namespace="nat")
        tool_call = [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "nat-gen", "arguments": "{}"},
            }
        ]
        try:
            batch = reg.execute_tool_calls(tool_call)[0]
        finally:
            reg._process_backend.shutdown()

        assert isinstance(batch, ErrorResult)
        assert "UnpicklableResultError" in batch.message
        assert "nat-gen" in batch.message
        assert "thread backend" in batch.message


def _reject(value: str):
    raise AssertionError(f"non-finite {value} in JSON body")


class TestNonFiniteFloats:
    """NaN and Infinity are not valid JSON; they become ``null`` (#346)."""

    @staticmethod
    def _strict_loads(text: str):
        def reject(value: str):
            raise AssertionError(f"non-finite {value} in JSON body: {text}")

        return json.loads(text, parse_constant=reject)

    def test_top_level_nan(self):
        reg = ToolRegistry()

        def metric() -> float:
            """Return a NaN metric."""
            return float("nan")

        reg.register(metric)
        text = _invoke_result(reg, "metric")
        assert self._strict_loads(text) is None

    def test_nan_in_container(self):
        reg = ToolRegistry()

        def metrics() -> dict:
            """Return metrics with non-finite values."""
            return {"loss": float("nan"), "ratios": [1.0, float("inf"), float("-inf")]}

        reg.register(metrics)
        parsed = self._strict_loads(_invoke_result(reg, "metrics"))
        assert parsed == {"loss": None, "ratios": [1.0, None, None]}

    def test_nan_in_dataclass(self):
        reg = ToolRegistry()

        def hit() -> SearchResult:
            """Return a dataclass holding a NaN score."""
            return SearchResult("T", "u", "c", float("nan"))

        reg.register(hit)
        parsed = self._strict_loads(_invoke_result(reg, "hit"))
        assert parsed["score"] is None

    def test_nan_in_nested_dataclass_list(self):
        reg = ToolRegistry()

        def hits() -> list[SearchResult]:
            """Return a list of dataclasses holding NaN scores."""
            return [SearchResult("T", "u", "c", float("inf"))]

        reg.register(hits)
        assert self._strict_loads(_invoke_result(reg, "hits"))[0]["score"] is None

    def test_finite_floats_unchanged(self):
        reg = ToolRegistry()

        def finite() -> dict:
            """Return finite floats."""
            return {"a": 0.5, "b": -0.0, "c": 1e308}

        reg.register(finite)
        parsed = self._strict_loads(_invoke_result(reg, "finite"))
        assert parsed == {"a": 0.5, "b": -0.0, "c": 1e308}

    def test_deeply_nested_result_walks_without_recursion(self):
        """The sanitiser must not impose its own depth limit (#347 review)."""
        from toolregistry.utils import _replace_non_finite

        depth = 5000
        root = current = []
        for _ in range(depth):
            child = []
            current.append(child)
            current = child
        current.append(float("nan"))

        result = _replace_non_finite(root)
        seen = 0
        node = result
        while len(node) == 1 and isinstance(node[0], list):
            node = node[0]
            seen += 1
        assert seen == depth
        assert node == [None]

    def test_self_referential_result_keeps_the_error_contract(self):
        """A cycle must raise the tool-named TypeError, not RecursionError."""
        from toolregistry.utils import encode_tool_result

        cyclic: list = []
        cyclic.append(cyclic)
        cyclic.append(float("nan"))

        with pytest.raises(TypeError, match="Circular reference"):
            encode_tool_result(cyclic, tool_name="cyclic_tool")

    def test_shared_container_is_sanitised_in_every_position(self):
        from toolregistry.utils import ToolResultJSONEncoder

        shared = [float("inf")]
        body = json.dumps([shared, shared], cls=ToolResultJSONEncoder)
        assert json.loads(body, parse_constant=_reject) == [[None], [None]]

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
    def test_non_finite_decimal_is_null_at_top_level(self, value):
        """str(Decimal('NaN')) is a bare NaN — not valid JSON (#347 review)."""
        from decimal import Decimal

        from toolregistry.utils import encode_tool_result

        body = encode_tool_result(Decimal(value), tool_name="t")
        assert json.loads(body, parse_constant=_reject) is None

    def test_non_finite_decimal_is_null_when_nested(self):
        from decimal import Decimal

        from toolregistry.utils import encode_tool_result

        body = encode_tool_result(
            {"d": Decimal("NaN"), "e": [Decimal("Infinity")]}, tool_name="t"
        )
        assert json.loads(body, parse_constant=_reject) == {"d": None, "e": [None]}

    def test_finite_decimal_is_unchanged(self):
        from decimal import Decimal

        from toolregistry.utils import encode_tool_result

        assert json.loads(encode_tool_result(Decimal("1.5"))) == 1.5
