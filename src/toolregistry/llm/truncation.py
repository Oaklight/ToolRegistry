"""Result size management: truncation and persistence for large tool outputs."""

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

#: Characters per token used to convert a token budget into characters.
#: This is a fixed estimate, not a tokenizer: a token limit is an
#: order-of-magnitude guard, while ``max_result_size`` is the exact limit.
CHARS_PER_TOKEN = 4

#: Marker budget reserved for the line-aware omission notice.
_LINE_MARKER_RESERVE = 48

#: Smallest per-string cap applied when a JSON document is pruned.
_MIN_STRING_LIMIT = 64

#: Key that carries omission counts inside a pruned JSON document.
_METADATA_KEY = "_truncation"


class TruncationStrategy(str, Enum):
    """Strategy for truncating large results.

    Attributes:
        HEAD: Keep only the first ``max_size`` characters.
        HEAD_TAIL: Keep the first and last portions, with a marker in the
            middle indicating how much was omitted.  For text with line
            structure the split is made on line boundaries.
    """

    HEAD = "head"
    HEAD_TAIL = "head_tail"


@dataclass
class TruncatedResult:
    """Container for a possibly-truncated tool result.

    Attributes:
        content: The (possibly truncated) text content.
        original_size: Original result size in characters.
        truncated: Whether truncation was applied.
        full_path: Path to the persisted full result, or None.
    """

    content: str
    original_size: int
    truncated: bool = False
    full_path: str | None = None

    def __str__(self) -> str:
        if not self.truncated:
            return self.content
        header_parts = [
            f"Truncated: {self.original_size} chars -> {len(self.content)} chars"
        ]
        if self.full_path:
            header_parts.append(f"full output: {self.full_path}")
        header = " | ".join(header_parts)
        return f"[{header}]\n{self.content}"


def _get_results_dir() -> str:
    """Return (and create) the directory for persisted full results."""
    results_dir = os.path.join(tempfile.gettempdir(), "toolregistry_results")
    os.makedirs(results_dir, exist_ok=True)
    return results_dir


def _persist_full_result(result_str: str, tool_name: str) -> str:
    """Write the full result to a temporary file and return its path.

    Args:
        result_str: The complete result string.
        tool_name: Name of the tool (used in the filename).

    Returns:
        Absolute path to the persisted file.
    """
    results_dir = _get_results_dir()
    content_hash = hashlib.sha256(result_str.encode()).hexdigest()[:12]
    timestamp = int(time.time())
    safe_name = tool_name.replace("/", "_").replace("\\", "_")
    filename = f"{safe_name}_{timestamp}_{content_hash}.txt"
    filepath = os.path.join(results_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(result_str)
    return filepath


# ---------------------------------------------------------------------------
# JSON-aware truncation
# ---------------------------------------------------------------------------


def _json_text(value: Any) -> str:
    """Serialize *value* compactly, so pruned output stays valid JSON."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _truncate_string(value: str, limit: int) -> tuple[str, int]:
    """Cap one string, returning ``(text, omitted_chars)``.

    The marker names how many characters of the value were dropped, so a
    reader can tell a truncated string from a short one.
    """
    if len(value) <= limit:
        return value, 0
    keep = max(0, limit - 16)
    for _ in range(3):
        omitted = len(value) - keep
        marker = f"...[+{omitted} chars]"
        next_keep = max(0, limit - len(marker))
        if next_keep == keep:
            break
        keep = next_keep
    omitted = len(value) - keep
    return value[:keep] + f"...[+{omitted} chars]", omitted


def _cap_strings(value: Any, limit: int) -> tuple[Any, int]:
    """Recursively cap strings deeper than *limit*.

    Returns the rewritten value and the number of characters dropped.
    """
    if isinstance(value, str):
        return _truncate_string(value, limit)
    if isinstance(value, dict):
        rewritten: dict[Any, Any] = {}
        omitted = 0
        for key, item in value.items():
            rewritten[key], item_omitted = _cap_strings(item, limit)
            omitted += item_omitted
        return rewritten, omitted
    if isinstance(value, list):
        rewritten_list: list[Any] = []
        omitted = 0
        for item in value:
            rewritten_item, item_omitted = _cap_strings(item, limit)
            rewritten_list.append(rewritten_item)
            omitted += item_omitted
        return rewritten_list, omitted
    return value, 0


def _omission_counts(omitted_items: int, omitted_chars: int) -> dict[str, int]:
    """Return the metadata payload carried by a pruned document."""
    return {"omitted_items": omitted_items, "omitted_chars": omitted_chars}


def _free_metadata_key(root: dict[Any, Any]) -> str:
    """Return a metadata key that does not collide with a key in *root*."""
    if _METADATA_KEY not in root:
        return _METADATA_KEY
    index = 1
    while f"{_METADATA_KEY}_{index}" in root:
        index += 1
    return f"{_METADATA_KEY}_{index}"


def _prune_dict(
    root: dict[Any, Any], max_size: int, omitted_chars: int
) -> tuple[str, int, int]:
    """Drop trailing items until the serialized document fits.

    Returns ``(text, omitted_items, omitted_chars)``.  The original keys are
    kept in order; the metadata key is added last.  Counting serialized
    sizes up front keeps the loop linear in the number of items.
    """
    keys = list(root)
    key_sizes = {key: len(_json_text(key)) for key in keys}
    value_sizes = {key: len(_json_text(root[key])) for key in keys}
    meta_key = _free_metadata_key(root)
    meta_key_size = len(_json_text(meta_key)) + 1
    omitted_items = 0
    body = sum(key_sizes[key] + 1 + value_sizes[key] for key in keys)

    def serialized_size() -> int:
        metadata = _omission_counts(omitted_items, omitted_chars)
        meta_size = meta_key_size + len(_json_text(metadata))
        separators = max(0, len(keys) - 1)
        comma_before_meta = 1 if keys else 0
        return 2 + body + separators + comma_before_meta + meta_size

    while keys and serialized_size() > max_size:
        key = keys.pop()
        entry_size = key_sizes[key] + 1 + value_sizes[key]
        body -= entry_size
        omitted_items += 1
        omitted_chars += entry_size

    data = {key: root[key] for key in keys}
    data[meta_key] = _omission_counts(omitted_items, omitted_chars)
    return _json_text(data), omitted_items, omitted_chars


def _prune_list(
    root: list[Any], max_size: int, omitted_chars: int
) -> tuple[str, int, int]:
    """Drop trailing elements until the serialized list fits.

    The result keeps the remaining elements and appends one sentinel object
    ``{"_truncation": {...}}``.  Returns ``(text, omitted_items,
    omitted_chars)``.
    """
    sizes = [len(_json_text(item)) for item in root]
    omitted_items = 0
    body = sum(sizes)

    def serialized_size() -> int:
        sentinel = len(
            _json_text({_METADATA_KEY: _omission_counts(omitted_items, omitted_chars)})
        )
        separators = max(0, len(sizes) - 1)
        comma_before_sentinel = 1 if sizes else 0
        return 2 + body + separators + comma_before_sentinel + sentinel

    while sizes and serialized_size() > max_size:
        piece = sizes.pop()
        body -= piece
        omitted_items += 1
        omitted_chars += piece

    data = list(root[: len(sizes)])
    data.append({_METADATA_KEY: _omission_counts(omitted_items, omitted_chars)})
    return _json_text(data), omitted_items, omitted_chars


def _truncate_json_value(value: Any, max_size: int) -> str:
    """Return JSON text for *value* that fits *max_size* where possible."""
    if isinstance(value, (dict, list)):
        string_limit = max(_MIN_STRING_LIMIT, max_size // 4)
        capped, string_omitted = _cap_strings(value, string_limit)
        if isinstance(capped, dict):
            text, _, _ = _prune_dict(capped, max_size, string_omitted)
        else:
            text, _, _ = _prune_list(capped, max_size, string_omitted)
        return text
    if isinstance(value, str):
        return _json_text(_truncate_string(value, max(1, max_size - 2))[0])
    return _json_text(value)


def _truncate_json_document(text: str, max_size: int) -> str | None:
    """Return pruned JSON text when *text* parses as JSON, else ``None``.

    A malformed document is not an error here: it falls through to the text
    path.  The returned text always parses with :func:`json.loads`.
    """
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None
    try:
        return _truncate_json_value(value, max_size)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Text truncation
# ---------------------------------------------------------------------------


def _head_tail_chars(text: str, max_size: int) -> str:
    """Legacy character head+tail split with a character-count marker."""
    marker = f"\n... (truncated {len(text) - max_size} chars) ...\n"
    available = max_size - len(marker)
    if available <= 0:
        # max_size too small for marker; fall back to pure head
        return text[:max_size]
    head_size = available // 2
    tail_size = available - head_size
    return text[:head_size] + marker + text[-tail_size:]


def _line_head_tail(text: str, lines: list[str], max_size: int) -> str | None:
    """Split *text* on line boundaries, or return ``None`` without structure.

    ``lines`` must come from ``text.splitlines(keepends=True)``.  Returns
    ``None`` when the budget cannot hold the marker or when a boundary line
    is too long, so the caller can fall back to a character split.
    """
    available = max_size - _LINE_MARKER_RESERVE
    if available <= 0:
        return None
    head_budget = available // 2
    tail_budget = available - head_budget
    if len(lines[0]) > head_budget or len(lines[-1]) > tail_budget:
        return None

    head_lines: list[str] = []
    head_used = 0
    for line in lines:
        if head_used + len(line) > head_budget:
            break
        head_lines.append(line)
        head_used += len(line)

    tail_lines: list[str] = []
    tail_used = 0
    for line in reversed(lines[len(head_lines) :]):
        if tail_used + len(line) > tail_budget:
            break
        tail_lines.append(line)
        tail_used += len(line)
    tail_lines.reverse()

    omitted_lines = len(lines) - len(head_lines) - len(tail_lines)
    omitted_chars = len(text) - head_used - tail_used
    marker = f"\n... ({omitted_lines} lines, {omitted_chars} chars omitted) ...\n"
    content = "".join(head_lines) + marker + "".join(tail_lines)
    if len(content) > max_size:
        return None
    return content


def _truncate_text(text: str, max_size: int, strategy: TruncationStrategy) -> str:
    """Truncate non-JSON text according to *strategy*."""
    if strategy == TruncationStrategy.HEAD:
        return text[:max_size]
    lines = text.splitlines(keepends=True)
    if len(lines) >= 3:
        content = _line_head_tail(text, lines, max_size)
        if content is not None:
            return content
    return _head_tail_chars(text, max_size)


def truncate_result(
    result_str: str,
    max_size: int,
    *,
    strategy: TruncationStrategy = TruncationStrategy.HEAD_TAIL,
    tool_name: str = "",
    persist: bool = True,
) -> TruncatedResult:
    """Truncate a string result if it exceeds ``max_size`` characters.

    A document that parses as JSON is pruned structurally so the output
    still parses: a dict root gains a ``_truncation`` key (renamed if the
    key already exists) with ``omitted_items``/``omitted_chars``, a list
    root gains one sentinel element with the same counts, and over-long
    strings inside the structure carry their own omission count.  Other
    text is truncated on line boundaries when it has useful line structure,
    with a marker naming the omitted lines and characters; text without
    line structure falls back to a character head+tail split.  Invalid JSON
    is treated as plain text and never raises.

    Args:
        result_str: The full result string.
        max_size: Maximum allowed size in characters.
        strategy: Truncation strategy for non-JSON text.
        tool_name: Tool name, used for the persisted filename.
        persist: Whether to write the full result to a temporary file.

    Returns:
        A ``TruncatedResult`` with the (possibly truncated) content and
        metadata about the operation.
    """
    if len(result_str) <= max_size:
        return TruncatedResult(
            content=result_str,
            original_size=len(result_str),
            truncated=False,
        )

    full_path = None
    if persist:
        full_path = _persist_full_result(result_str, tool_name)

    content = _truncate_json_document(result_str, max_size)
    if content is None:
        content = _truncate_text(result_str, max_size, strategy)

    return TruncatedResult(
        content=content,
        original_size=len(result_str),
        truncated=True,
        full_path=full_path,
    )
