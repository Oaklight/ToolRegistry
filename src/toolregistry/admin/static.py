"""Static assets for the admin panel.

The UI is a shell (``admin.html``) plus the stylesheets under ``css/`` and the
scripts under ``js/``, all shipped as package data and served from the
``assets/`` URL prefix.  They are read from the package rather than embedded so
there is one source of truth: an earlier embedded copy drifted from
``admin.html``, and fixes (for example the runtime warnings UI) never reached
the panel the server actually served.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import PurePosixPath

_ADMIN_PACKAGE = files("toolregistry.admin")

#: The shell document served at ``/``.
ADMIN_HTML: str = _ADMIN_PACKAGE.joinpath("admin.html").read_text(encoding="utf-8")


def read_shell() -> str:
    """Return the shell document as it is on disk right now.

    The panel is edited live during development; reading per request keeps a
    running server in step with the file, the same way the css/ and js/ assets
    are served.  ``ADMIN_HTML`` remains the import-time snapshot for callers
    that only need the text.
    """
    return _ADMIN_PACKAGE.joinpath("admin.html").read_text(encoding="utf-8")


#: Directories a request may read from.  Anything else is not an asset.
_ASSET_DIRS = ("css", "js")

#: Suffix → media type.  The whitelist doubles as the traversal guard: a name
#: with any other suffix is rejected before the filesystem is consulted.
_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


def read_asset(relative: str) -> tuple[str, str] | None:
    """Read a shipped asset by its ``assets/``-relative path.

    Args:
        relative: Path such as ``css/base.css`` or ``js/core/theme.js``.

    Returns:
        ``(text, content_type)`` when *relative* names a file that ships with
        the package, otherwise ``None``.  Requests that try to leave the asset
        directories (``..``, absolute paths, backslashes) return ``None``
        rather than raising.
    """
    if not relative or "\\" in relative or relative.startswith("/"):
        return None
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in ("..", ".") for part in path.parts):
        return None
    if len(path.parts) < 2 or path.parts[0] not in _ASSET_DIRS:
        return None
    content_type = _CONTENT_TYPES.get(path.suffix)
    if content_type is None:
        return None

    resource = _ADMIN_PACKAGE.joinpath(*path.parts)
    if not resource.is_file():
        return None
    return resource.read_text(encoding="utf-8"), content_type
