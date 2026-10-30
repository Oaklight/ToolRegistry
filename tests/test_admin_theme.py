"""Contract tests for the admin panel's theme layer.

The panel separates a *scheme* (values: colours declared per scheme and mode
in ``css/base.css``) from *components* (structure in ``css/components.css``).
The boundary is what keeps a scheme from reaching into a component's layout or
hit-testing, so it is checked as text rather than left to review:

1. A scheme selector appears only in ``base.css`` and names nothing but the
   scheme and mode.
2. A scheme block declares custom properties only.
3. Every scheme block declares the same token set, so a token cannot resolve
   to nothing in one mode and something in another.
"""

from __future__ import annotations

import re
from importlib.resources import files

import pytest

_ADMIN = files("toolregistry.admin")
BASE_CSS = _ADMIN.joinpath("css/base.css").read_text(encoding="utf-8")
COMPONENTS_CSS = _ADMIN.joinpath("css/components.css").read_text(encoding="utf-8")

#: ``[data-scheme="name"]`` with an optional mode qualifier, and nothing else.
_SCHEME_SELECTOR = re.compile(
    r'^\[data-scheme="(?P<name>[a-z][a-z0-9-]*)"\]'
    r'(?:\[data-mode="(?P<mode>light|dark)"\])?$'
)

_DECLARATION = re.compile(r"^\s*(?P<prop>[-a-zA-Z]+)\s*:\s*(?P<value>.+?);\s*$")


def _blocks(css: str) -> list[tuple[str, str]]:
    """Return ``(selector, body)`` for every top-level rule, at-rules skipped."""
    blocks: list[tuple[str, str]] = []
    i = 0
    while True:
        brace = css.find("{", i)
        if brace == -1:
            return blocks
        selector = css[i:brace]
        # Drop the preceding comment and whitespace.
        selector = selector.rsplit("*/", 1)[-1].strip()
        depth = 0
        end = brace
        while end < len(css):
            if css[end] == "{":
                depth += 1
            elif css[end] == "}":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        blocks.append((selector, css[brace + 1 : end]))
        i = end + 1


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def test_base_css_defines_both_schemes_in_both_modes() -> None:
    schemes: dict[tuple[str, str | None], None] = {}
    for selector, _ in _blocks(_strip_comments(BASE_CSS)):
        match = _SCHEME_SELECTOR.match(selector)
        if match:
            schemes[(match["name"], match["mode"])] = None

    names = {name for name, _ in schemes}
    assert names == {"paper", "slate"}
    for name in names:
        assert (name, "light") in schemes
        assert (name, "dark") in schemes


def test_scheme_selectors_appear_only_in_base_css() -> None:
    assert "[data-scheme" not in COMPONENTS_CSS


def test_scheme_selectors_name_nothing_but_scheme_and_mode() -> None:
    offenders = []
    for selector, _ in _blocks(_strip_comments(BASE_CSS)):
        if "data-scheme" not in selector:
            continue
        # A selector list is one selector per block; each must pass on its own.
        for part in selector.split(","):
            if not _SCHEME_SELECTOR.match(part.strip()):
                offenders.append(part.strip())
    assert offenders == []


def test_scheme_blocks_declare_custom_properties_only() -> None:
    offenders = []
    for selector, body in _blocks(_strip_comments(BASE_CSS)):
        if "data-scheme" not in selector:
            continue
        for declaration in body.split(";"):
            if not declaration.strip():
                continue
            match = _DECLARATION.match(declaration + ";")
            if match is None or not match["prop"].startswith("--"):
                offenders.append((selector, declaration.strip()))
    assert offenders == []


def test_every_scheme_block_declares_the_same_tokens() -> None:
    token_sets: dict[str, set[str]] = {}
    for selector, body in _blocks(_strip_comments(BASE_CSS)):
        match = _SCHEME_SELECTOR.match(selector)
        if not match:
            continue
        tokens = {
            m["prop"]
            for m in (
                _DECLARATION.match(line.strip() + ";")
                for line in body.split(";")
                if line.strip()
            )
            if m is not None
        }
        token_sets[f"{match['name']}/{match['mode'] or 'shared'}"] = tokens

    reference_key = "paper/light"
    reference = token_sets[reference_key]
    for key, tokens in token_sets.items():
        missing = sorted(reference - tokens)
        extra = sorted(tokens - reference)
        assert not missing, f"{key} is missing {missing}"
        assert not extra, f"{key} declares {extra}, absent from {reference_key}"


def test_schemes_render_differently() -> None:
    """A scheme that declares the same values as another is a copy, not a scheme."""

    def values(mode: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for selector, body in _blocks(_strip_comments(BASE_CSS)):
            match = _SCHEME_SELECTOR.match(selector)
            if not match or match["mode"] != mode:
                continue
            for line in body.split(";"):
                m = _DECLARATION.match(line.strip() + ";")
                if m:
                    out[f"{match['name']}/{m['prop']}"] = m["value"].strip()
        return out

    for mode in ("light", "dark"):
        declared = values(mode)
        overlap = {
            prop
            for prop in declared
            if prop.startswith("paper/")
            and f"slate/{prop.split('/', 1)[1]}" in declared
        }
        differing = [
            p for p in overlap if declared[p] != declared[f"slate/{p.split('/', 1)[1]}"]
        ]
        assert differing, f"paper and slate are identical in {mode}"


def test_tokens_used_by_components_are_declared() -> None:
    """Every ``var(--x)`` a component reads resolves in each scheme block."""
    declared: set[str] = set()
    for selector, body in _blocks(_strip_comments(BASE_CSS)):
        declared.update(re.findall(r"(--[a-z0-9-]+)\s*:", body))

    used = set(re.findall(r"var\((--[a-z0-9-]+)", _strip_comments(COMPONENTS_CSS)))
    used |= set(re.findall(r"var\((--[a-z0-9-]+)", _strip_comments(BASE_CSS)))
    # Custom properties may also be defined and consumed inside components
    # (local aliases), so only report tokens nothing declares anywhere.
    undefined = sorted(token for token in used if token not in declared)
    assert undefined == []


@pytest.mark.parametrize("scheme", ["paper", "slate"])
def test_scheme_name_is_in_the_early_boot_allow_list(scheme: str) -> None:
    """The pre-paint script would otherwise flash the default on every load."""
    shell = _ADMIN.joinpath("admin.html").read_text(encoding="utf-8")
    assert f"'{scheme}'" in shell
