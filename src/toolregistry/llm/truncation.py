"""Result size management: truncation and persistence for large tool outputs."""

import hashlib
import os
import tempfile
import time
from dataclasses import dataclass
from enum import Enum


class TruncationStrategy(str, Enum):
    """Strategy for truncating large results.

    Attributes:
        HEAD: Keep only the first ``max_size`` characters.
        HEAD_TAIL: Keep the first and last portions, with a marker in the
            middle indicating how many characters were omitted.
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


def truncate_result(
    result_str: str,
    max_size: int,
    *,
    strategy: TruncationStrategy = TruncationStrategy.HEAD_TAIL,
    tool_name: str = "",
    persist: bool = True,
) -> TruncatedResult:
    """Truncate a string result if it exceeds ``max_size`` characters.

    Args:
        result_str: The full result string.
        max_size: Maximum allowed size in characters.
        strategy: Truncation strategy to apply.
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

    if strategy == TruncationStrategy.HEAD:
        content = result_str[:max_size]
    else:
        # HEAD_TAIL: split budget between head and tail with a marker
        marker = f"\n... (truncated {len(result_str) - max_size} chars) ...\n"
        available = max_size - len(marker)
        if available <= 0:
            # max_size too small for marker; fall back to pure head
            content = result_str[:max_size]
        else:
            head_size = available // 2
            tail_size = available - head_size
            content = result_str[:head_size] + marker + result_str[-tail_size:]

    return TruncatedResult(
        content=content,
        original_size=len(result_str),
        truncated=True,
        full_path=full_path,
    )
