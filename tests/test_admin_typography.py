"""Typography contract for the admin panel.

Every page of the panel draws its text from one four-step scale declared in
``css/base.css`` -- ``--text-display`` (stat numbers), ``--text-body`` (data,
controls, headings), ``--text-small`` (hints, code, descriptions) and
``--text-micro`` (badges, table headers, counts).  The contract is checked as
text, the way the theme contract is, because the drift it prevents is
invisible in review: one panel declaring ``0.8125rem`` reads as "slightly
different" next to its neighbours, yet no single page looks broken on its own.

The only exceptions are two glyph rules, where ``font-size`` sizes a symbol
rather than a line of text.
"""

from __future__ import annotations

import re
from importlib.resources import files

_ADMIN = files("toolregistry.admin")

#: The scale.  Everything that is text uses one of these steps.
SCALE = ("--text-display", "--text-body", "--text-small", "--text-micro")

#: ``font-size`` here sizes a glyph (the modal's ×, the empty-state mark).
GLYPH_SELECTORS = {".modal-close", ".empty-state-icon"}

_FONT_SIZE = re.compile(r"font-size\s*:\s*([^;]+)")


def _rules(css: str) -> list[tuple[str, str]]:
    """Return ``(selector, body)`` for every rule in *css*, comments removed.

    Bodies of at-rules (``@media``) still contain their nested rules; scanning
    them for declarations is intended, since a nested ``font-size`` must obey
    the same contract.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    rules: list[tuple[str, str]] = []
    i = 0
    while (brace := css.find("{", i)) != -1:
        selector = css[i:brace].strip()
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
        rules.append((selector, css[brace + 1 : end]))
        i = end + 1
    return rules


def _js_sources(node=_ADMIN.joinpath("js"), prefix: str = "") -> list[tuple[str, str]]:
    """Return ``(name, text)`` for every shipped script, recursively."""
    found: list[tuple[str, str]] = []
    for child in sorted(node.iterdir(), key=lambda item: item.name):
        name = f"{prefix}{child.name}"
        if child.is_dir():
            found.extend(_js_sources(child, name + "/"))
        elif child.name.endswith(".js"):
            found.append((name, child.read_text(encoding="utf-8")))
    return found


def _inline_sources() -> list[tuple[str, str]]:
    shell = _ADMIN.joinpath("admin.html").read_text(encoding="utf-8")
    return [("admin.html", shell), *_js_sources()]


def test_root_declares_the_typography_scale() -> None:
    base = _ADMIN.joinpath("css/base.css").read_text(encoding="utf-8")
    root = next(body for selector, body in _rules(base) if selector == ":root")
    for token in SCALE:
        assert re.search(rf"{re.escape(token)}\s*:\s*[^;]+;", root), token


def test_css_text_sizes_come_from_the_scale() -> None:
    offenders: list[tuple[str, str, str]] = []
    for name in ("css/base.css", "css/components.css"):
        css = _ADMIN.joinpath(name).read_text(encoding="utf-8")
        for selector, body in _rules(css):
            for match in _FONT_SIZE.finditer(body):
                value = match.group(1).strip()
                if value == "inherit" or "var(--text-" in value:
                    continue
                if selector in GLYPH_SELECTORS:
                    continue
                offenders.append((name, selector, value))
    assert offenders == []


def test_inline_styles_come_from_the_scale() -> None:
    offenders: list[tuple[str, str]] = []
    for name, text in _inline_sources():
        for match in re.finditer(r"font-size\s*:\s*([^;\"']+)", text):
            value = match.group(1).strip()
            if "var(--text-" not in value:
                offenders.append((name, value))
    assert offenders == []


def test_every_scale_step_is_used() -> None:
    """A step nothing reads is a size waiting to be invented twice."""
    text = "".join(
        [text for _, text in _inline_sources()]
        + [
            _ADMIN.joinpath(path).read_text(encoding="utf-8")
            for path in ("css/base.css", "css/components.css")
        ]
    )
    for token in SCALE:
        assert f"var({token})" in text, f"{token} is declared but never used"
