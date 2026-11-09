"""The structure sections of AGENTS.md must name paths that exist.

`AGENTS.md` is the first file every agent reads, so a layout that describes
modules removed in an earlier refactor costs real time.  These tests pin the
document to the tree: each layout entry, each backticked ``src/toolregistry``
path and each module name in a backtick must resolve on disk.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
TREE_HEADING = "## Repository layout"

#: Documentation lives on orphan branches mounted as worktrees locally; a
#: plain CI checkout does not contain them, so the layout may name them but
#: their absence is not a stale path.
_ORPHAN_WORKTREES = {"docs_en", "docs_zh"}


def _tree_paths(text: str) -> list[str]:
    """Return every path named in the repository-layout code block."""
    start = text.index("```", text.index(TREE_HEADING))
    block = text[start + 3 : text.index("```", start + 3)]

    root: str | None = None
    stack: list[str] = []
    paths: list[str] = []
    for line in block.splitlines():
        match = re.match(r"^(?P<prefix>[│\s]*)(?:[├└]── )?(?P<name>[^\s#]+)", line)
        if match is None:
            continue
        name = match.group("name").rstrip(",")
        if "├──" not in line and "└──" not in line:
            # The block root, then the root-relative paths below the tree.
            if root is None:
                root = name.rstrip("/")
            else:
                paths.append(name.rstrip("/"))
            continue
        depth = len(match.group("prefix")) // 4
        if depth == 0:
            stack = [root]
        else:
            stack = stack[: depth + 1]
        paths.append("/".join([*stack, name.rstrip("/")]))
        if name.endswith("/"):
            stack.append(name.rstrip("/"))
    return paths


def test_layout_tree_paths_exist() -> None:
    """Every entry in the layout tree is a real file or directory."""
    paths = _tree_paths(AGENTS.read_text(encoding="utf-8"))

    assert paths
    missing = sorted(
        path
        for path in paths
        if Path(path).parts[0] not in _ORPHAN_WORKTREES and not (ROOT / path).exists()
    )
    assert not missing


def test_backticked_source_paths_exist() -> None:
    """Every src/toolregistry path named in prose or a table exists."""
    text = AGENTS.read_text(encoding="utf-8")
    paths = set(re.findall(r"`(src/toolregistry/[^`]+)`", text))

    assert paths
    missing = []
    for path in paths:
        cleaned = path.rstrip("/").removesuffix("/**")
        if "*" in cleaned:
            continue
        if not (ROOT / cleaned).exists():
            missing.append(path)
    assert not missing


def test_backticked_module_names_exist() -> None:
    """Every module name in a backtick resolves at the root or in the package."""
    text = AGENTS.read_text(encoding="utf-8")
    names = set(re.findall(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.py)`", text))

    assert names
    missing = sorted(
        name
        for name in names
        if not (ROOT / name).exists()
        and not (ROOT / "src/toolregistry" / name).exists()
    )
    assert not missing
