"""Result size management: truncation and persistence for large tool outputs."""

import contextlib
import json
import os
import re
import secrets
import tempfile
import threading
import time
from collections.abc import Callable
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

#: Default lifetime of a persisted result, in seconds (24 hours).
DEFAULT_RESULT_TTL_SECONDS = 24 * 60 * 60.0

#: Default total size of the persistence directory, in bytes (64 MiB).
DEFAULT_RESULT_QUOTA_BYTES = 64 * 1024 * 1024

#: Characters returned by one ``read_result`` call when *limit* is omitted.
DEFAULT_READ_RESULT_LIMIT = 8000

#: Characters decoded per step while skipping to a read offset.
_READ_CHUNK = 65536

_RESULT_ID_PATTERN = re.compile(r"^res_[0-9a-f]{12}$")


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
        full_path: Host path to the persisted full result.  For programmatic
            callers only: :meth:`__str__` never renders it, because the
            string form is placed in the model context.
        result_id: Opaque id (``res_<12 hex>``) under which the full result
            can be read back with the ``read_result`` tool.  ``None`` when
            the result was not persisted.
    """

    content: str
    original_size: int
    truncated: bool = False
    full_path: str | None = None
    result_id: str | None = None

    def __str__(self) -> str:
        if not self.truncated:
            return self.content
        header_parts = [
            f"Truncated: {self.original_size} chars -> {len(self.content)} chars"
        ]
        if self.result_id:
            header_parts.append(
                f"full output: {self.result_id} (read it with read_result)"
            )
        elif self.full_path:
            header_parts.append("full output: persisted")
        header = " | ".join(header_parts)
        return f"[{header}]\n{self.content}"


class ResultStore:
    """Per-run storage for full tool results.

    Files live in a private directory, are created with mode ``0600``,
    expire after *ttl* seconds, and are evicted oldest-first when the
    directory would exceed *quota* bytes.  An id is opaque
    (``res_<12 hex>``) and the filesystem path is never placed in a
    truncation header.

    Args:
        root: Directory to store results in.  ``None`` creates a fresh
            per-run directory under the system temp dir with mode ``0700``.
        ttl: Seconds a result stays readable.
        quota: Total bytes the directory may hold.
        clock: Wall-clock source, injectable for tests.

    Raises:
        ValueError: If *ttl* is not positive or *quota* is negative.
    """

    def __init__(
        self,
        root: str | None = None,
        *,
        ttl: float = DEFAULT_RESULT_TTL_SECONDS,
        quota: int = DEFAULT_RESULT_QUOTA_BYTES,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        if quota < 0:
            raise ValueError("quota must be non-negative")
        self.root = (
            root
            if root is not None
            else tempfile.mkdtemp(prefix="toolregistry-results-")
        )
        os.makedirs(self.root, mode=0o700, exist_ok=True)
        self.ttl = ttl
        self.quota = quota
        self._clock = clock
        self._lock = threading.Lock()

    def put(self, text: str) -> tuple[str, str]:
        """Store *text*, returning ``(result_id, path)``.

        Cleanup runs first: expired files are removed, then the oldest
        files are evicted until the directory fits the quota.  The file just
        written is never evicted, even when it alone exceeds the quota.
        """
        with self._lock:
            self._cleanup_locked()
            for _ in range(8):
                result_id = f"res_{secrets.token_hex(6)}"
                path = os.path.join(self.root, f"{result_id}.txt")
                try:
                    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    continue
                try:
                    with os.fdopen(handle, "w", encoding="utf-8") as stream:
                        stream.write(text)
                    # Timestamps follow the store clock so TTL and eviction
                    # order are testable without sleeping.
                    now = self._clock()
                    os.utime(path, (now, now))
                except BaseException:
                    with contextlib.suppress(OSError):
                        os.unlink(path)
                    raise
                self._enforce_quota_locked(keep=path)
                return result_id, path
        raise RuntimeError("could not allocate a result id")

    def path_for(self, result_id: str) -> str:
        """Return the host path for *result_id*.

        Raises:
            ValueError: If *result_id* is not an opaque result id.
        """
        if not isinstance(result_id, str) or not _RESULT_ID_PATTERN.fullmatch(
            result_id
        ):
            raise ValueError(f"invalid result id {result_id!r}")
        return os.path.join(self.root, f"{result_id}.txt")

    def read(
        self,
        result_id: str,
        offset: int = 0,
        limit: int = DEFAULT_READ_RESULT_LIMIT,
    ) -> str:
        """Return one character slice of a stored result.

        Args:
            result_id: Opaque id returned by :meth:`put`.
            offset: Character offset to start at.
            limit: Maximum characters to return.

        Raises:
            ValueError: If the id is invalid or unknown, the file expired,
                or *offset*/*limit* is not a non-negative integer.
        """
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        path = self.path_for(result_id)
        try:
            if self._clock() - os.path.getmtime(path) > self.ttl:
                with contextlib.suppress(OSError):
                    os.unlink(path)
                raise ValueError(f"result id {result_id!r} has expired")
            with open(path, encoding="utf-8") as stream:
                remaining = offset
                while remaining > 0:
                    skipped = len(stream.read(min(remaining, _READ_CHUNK)))
                    if skipped == 0:
                        return ""
                    remaining -= skipped
                return stream.read(limit)
        except FileNotFoundError as exc:
            raise ValueError(f"unknown result id {result_id!r}") from exc

    def _cleanup_locked(self) -> None:
        """Remove expired files.  Holds the lock."""
        now = self._clock()
        for path in self._files():
            with contextlib.suppress(OSError):
                if now - os.path.getmtime(path) > self.ttl:
                    os.unlink(path)

    def _enforce_quota_locked(self, keep: str) -> None:
        """Evict the oldest files until the directory fits.  Holds the lock."""
        entries: list[tuple[float, int, str]] = []
        for path in self._files():
            try:
                stat = os.stat(path)
            except OSError:
                continue
            entries.append((stat.st_mtime, stat.st_size, path))
        total = sum(size for _, size, _ in entries)
        for _, size, path in sorted(entries):
            if total <= self.quota:
                break
            if path == keep:
                continue
            with contextlib.suppress(OSError):
                os.unlink(path)
                total -= size

    def _files(self) -> list[str]:
        """Return the stored result files, ignoring foreign files."""
        try:
            names = os.listdir(self.root)
        except OSError:
            return []
        paths = []
        for name in names:
            if name.endswith(".txt") and _RESULT_ID_PATTERN.fullmatch(name[:-4]):
                paths.append(os.path.join(self.root, name))
        return paths


_DEFAULT_STORE: ResultStore | None = None
_DEFAULT_STORE_LOCK = threading.Lock()


def default_result_store() -> ResultStore:
    """Return the process-wide store used by ``truncate_result(persist=True)``."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        with _DEFAULT_STORE_LOCK:
            if _DEFAULT_STORE is None:
                _DEFAULT_STORE = ResultStore()
    return _DEFAULT_STORE


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
    """Return pruned JSON text when *text* parses as JSON and fits.

    A malformed document is not an error here: it falls through to the text
    path.  So does a document whose pruned form still exceeds *max_size*,
    for example when the omission metadata alone is larger than the budget.
    The returned text always parses with :func:`json.loads` and is never
    longer than *max_size*.

    ``RecursionError`` is caught as well: :func:`json.loads` and the
    recursive string capping both raise it on deeply nested documents, and
    such a result must fall back to text truncation instead of escaping.
    """
    try:
        value = json.loads(text)
    except (TypeError, ValueError, RecursionError):
        return None
    try:
        pruned = _truncate_json_value(value, max_size)
    except (TypeError, ValueError, RecursionError):
        return None
    if len(pruned) > max_size:
        return None
    return pruned


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
    store: ResultStore | None = None,
) -> TruncatedResult:
    """Truncate a string result if it exceeds ``max_size`` characters.

    A document that parses as JSON is pruned structurally when the pruned
    form fits ``max_size``, so the output still parses: a dict root gains a
    ``_truncation`` key (renamed if the key already exists) with
    ``omitted_items``/``omitted_chars``, a list root gains one sentinel
    element with the same counts, and over-long strings inside the structure
    carry their own omission count.  When the pruned form cannot fit — for
    example when the omission metadata alone is larger than the budget — the
    document is truncated as text and may no longer parse.  Other text is
    truncated on line boundaries when it has useful line structure, with a
    marker naming the omitted lines and characters; text without line
    structure falls back to a character head+tail split.  Invalid JSON and
    deeply nested JSON are treated as plain text and never raise.

    The returned content is never longer than ``max_size``.

    Args:
        result_str: The full result string.
        max_size: Maximum allowed size in characters.
        strategy: Truncation strategy for non-JSON text.
        tool_name: Tool name.  Retained for callers that label results;
            stored files are named by their opaque result id.
        persist: Whether to store the full result.
        store: Store to write to.  ``None`` uses
            :func:`default_result_store`, a process-wide per-run store.

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
    result_id = None
    if persist:
        result_id, full_path = (store or default_result_store()).put(result_str)

    content = _truncate_json_document(result_str, max_size)
    if content is None:
        content = _truncate_text(result_str, max_size, strategy)

    return TruncatedResult(
        content=content,
        original_size=len(result_str),
        truncated=True,
        full_path=full_path,
        result_id=result_id,
    )
