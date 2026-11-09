"""JSON encoding for values a tool returns.

The encoder projects the Python values tools commonly return -- enums, paths,
decimals, dates, sets, dataclasses, Pydantic models, array-likes -- to JSON,
and replaces non-finite floats with ``null``.  It is re-exported from
:mod:`toolregistry.utils`, which is the documented compatibility surface.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import math
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

__all__ = ["ToolResultJSONEncoder", "encode_tool_result"]


def _sanitise_float(value: Any) -> Any:
    """Return a finite float unchanged and a non-finite one as ``None``."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _copy_into(container: Any, key: Any, item: Any, state: dict) -> None:
    """Append or assign *item*, copying a JSON container if it is new."""
    if not isinstance(item, (dict, list, tuple)):
        value = _sanitise_float(item)
    else:
        value = state["copies"].get(id(item))
        if value is None:
            value = {} if isinstance(item, dict) else []
            state["copies"][id(item)] = value
            state["stack"].append((item, value))
    if isinstance(container, dict):
        container[key] = value
    else:
        container.append(value)


def _replace_non_finite(value: Any) -> Any:
    """Return *value* with non-finite floats replaced by ``None``.

    Walks the JSON containers ``json`` traverses itself.  Set elements and
    dataclass fields are projected by :class:`ToolResultJSONEncoder`, which
    sanitizes its own output, so they are left untouched here.

    The walk is iterative and keeps one copy per container identity, for two
    reasons.  A deeply nested result must not exhaust the interpreter's
    recursion limit, which ``json``'s own C encoder does not; and a
    self-referential result must reach ``json``'s circular-reference check so
    the caller sees the documented error instead of a ``RecursionError``
    raised from here.
    """
    if not isinstance(value, (dict, list, tuple)):
        return _sanitise_float(value)

    root: Any = {} if isinstance(value, dict) else []
    state = {"copies": {id(value): root}, "stack": [(value, root)]}
    while state["stack"]:
        source, target = state["stack"].pop()
        items = source.items() if isinstance(source, dict) else enumerate(source)
        for key, item in items:
            _copy_into(target, key, item, state)
    return root


class ToolResultJSONEncoder(json.JSONEncoder):
    """JSON encoder for values returned by tools.

    Projects common non-JSON-native Python values to a JSON-safe
    representation.  ``json`` traverses containers itself, so this only
    needs to handle the leaf values it cannot serialize.

    Handled values:

    - ``Enum`` members -> their ``.value``
    - ``pathlib.Path`` -> ``str``
    - ``Decimal`` / ``UUID`` -> ``str``
    - ``datetime`` / ``date`` / ``time`` -> ISO 8601 string
    - ``bytes`` -> base64-encoded ASCII string
    - ``set`` / ``frozenset`` -> JSON array, ordered by ``repr`` so the
      encoding is reproducible across processes for orderable and
      mixed-type elements alike (tuples are native to JSON)
    - dataclass instances -> :func:`dataclasses.asdict`
    - Pydantic v2 models (``model_dump``), v1 models (``dict``), any
      object exposing a zero-argument ``to_dict`` -> ``dict``, and
      array-like objects exposing ``tolist`` (numpy arrays, torch
      tensors) -> list

    Whatever ``tolist`` returns is serialized by ``json`` normally, so a
    non-native element inside it is routed back through this encoder.

    Non-finite floats (``NaN``, ``Infinity``, ``-Infinity``) are written as
    ``null``.  ``json`` would otherwise emit the bare constants, which are
    not valid JSON: ``JSON.parse``, Go's ``encoding/json`` and serde all
    reject them, so a tool returning a metric computed from an empty set
    would produce a body a conforming client cannot read.  FastAPI's
    encoder and the JSON spec's recommendation both use ``null``.

    Anything else has no JSON projection and raises ``TypeError``.
    """

    def iterencode(self, o: Any, _one_shot: bool = False):  # noqa: ANN401
        """Encode *o* after replacing non-finite floats with ``null``."""
        return super().iterencode(_replace_non_finite(o), _one_shot)

    def default(self, o: Any) -> Any:
        """Project *o* to JSON-native values, sanitising non-finite floats."""
        return _replace_non_finite(self._project(o))

    def _project(self, o: Any) -> Any:
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, Decimal):
            return None if not o.is_finite() else str(o)
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        if isinstance(o, bytes):
            return base64.b64encode(o).decode("ascii")
        if isinstance(o, (set, frozenset)):
            # A total order: ``repr`` is always a string, so mixed-type
            # elements sort deterministically instead of following
            # interpreter (process-seeded) iteration order.
            return sorted(o, key=repr)
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        for attr in ("model_dump", "to_dict", "dict", "tolist"):
            method = getattr(o, attr, None)
            if callable(method):
                return method()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


# Types that may be emitted as a bare string without JSON-quoting at the
# top level: their ``str()`` already matches the encoder's projection, so
# the historical plain-string form is preserved.  ``datetime`` is excluded
# even though it subclasses ``date`` -- ``str()`` uses a space separator
# while ``isoformat()`` uses ``T``.  ``Enum`` is handled before this
# allowlist (see ``encode_tool_result``) so a str-mixin member is not
# swallowed by the plain-``str`` branch: ``str()`` yields ``Color.RED`` /
# ``S.A``, exactly the unparseable forms this encoder exists to remove.
# ``bytes`` is likewise excluded on purpose.
_STR_LIKE_SCALARS = (str, Path, Decimal, uuid.UUID, date, time)


def encode_tool_result(result: Any, *, tool_name: str = "") -> str:
    """Encode a tool result to a string suitable for the wire.

    Plain strings pass through unchanged.  Values in the str-like scalar
    allowlist keep their historical ``str()`` textual form.  ``Enum``
    members are projected through ``.value`` at the top level, matching
    their nested projection; this also covers ``IntEnum`` and ``StrEnum``,
    whose ``int`` / ``str`` base would otherwise let the plain scalar
    branch return the bare member.  Everything else -- including ``bytes``
    or ``datetime`` -- is serialized with :class:`ToolResultJSONEncoder`,
    so dataclasses, Pydantic models, paths, and other common types produce
    valid JSON instead of Python ``repr`` text, and the top-level and
    nested projections agree.

    Args:
        result: Raw value returned by a tool.
        tool_name: Tool name, used in the error message when *result* (or
            a value nested inside it) cannot be encoded.

    Returns:
        The encoded result string.

    Raises:
        TypeError: If *result* has no JSON projection.  The message names
            the tool and the offending type, and suggests how to make the
            value encodable.
    """
    if isinstance(result, Enum):
        # Must precede the ``str`` check: ``StrEnum`` (and any
        # ``str``-mixin enum) is a ``str`` instance, and returning the
        # member would put ``S.A`` on the wire instead of ``"a"``.
        return json.dumps(result.value, cls=ToolResultJSONEncoder)
    if isinstance(result, str):
        return result
    if isinstance(result, Decimal) and not result.is_finite():
        # str(Decimal("NaN")) is the bare NaN, which is not valid JSON.
        return "null"
    if isinstance(result, _STR_LIKE_SCALARS) and not isinstance(result, datetime):
        return str(result)
    try:
        return json.dumps(result, cls=ToolResultJSONEncoder)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"Tool {tool_name!r} returned a value that cannot be encoded to JSON "
            f"({exc}). Add a to_dict() or model_dump() method to the returned "
            f"type, expose tolist(), or return a str."
        ) from exc
