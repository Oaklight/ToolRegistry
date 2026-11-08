"""Static assets for the admin panel.

The UI is a shell (``admin.html``) plus the stylesheets under ``css/`` and the
scripts under ``js/``, all shipped as package data and served from the
``assets/`` URL prefix.  They are read from the package rather than embedded so
there is one source of truth: an earlier embedded copy drifted from
``admin.html``, and fixes (for example the runtime warnings UI) never reached
the panel the server actually served.
"""

from __future__ import annotations

from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path, PurePosixPath

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


def content_type_for(suffix: str) -> str | None:
    """Return the media type served for *suffix*, or ``None``.

    Args:
        suffix: A file suffix including the leading dot, such as ``.js``.

    Returns:
        The media type when the suffix is on the asset whitelist.
    """
    return _CONTENT_TYPES.get(suffix)


def read_asset(
    relative: str,
    extension_assets: Mapping[str, Path] | None = None,
) -> tuple[str, str] | None:
    """Read an asset by its ``assets/``-relative path.

    Library assets live under ``css/`` and ``js/`` inside the package.
    Extension assets live under ``ext/<name>/`` in the directory the extension
    declared; *extension_assets* maps a name to that directory.

    Args:
        relative: Path such as ``css/base.css``, ``js/core/theme.js`` or
            ``ext/clock/main.js``.
        extension_assets: Extension name → resolved asset directory.  Names
            absent from the mapping are refused.

    Returns:
        ``(text, content_type)`` when *relative* names a file that ships with
        the package or belongs to a mounted extension, otherwise ``None``.
        Requests that try to leave the asset directories (``..``, absolute
        paths, backslashes) return ``None`` rather than raising.
    """
    if not relative or "\\" in relative or relative.startswith("/"):
        return None
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in ("..", ".") for part in path.parts):
        return None

    if path.parts[:1] == ("ext",):
        return _read_extension_asset(path, extension_assets or {})

    if len(path.parts) < 2 or path.parts[0] not in _ASSET_DIRS:
        return None
    content_type = content_type_for(path.suffix)
    if content_type is None:
        return None

    resource = _ADMIN_PACKAGE.joinpath(*path.parts)
    if not resource.is_file():
        return None
    return resource.read_text(encoding="utf-8"), content_type


def _read_extension_asset(
    path: PurePosixPath,
    extension_assets: Mapping[str, Path],
) -> tuple[str, str] | None:
    """Read ``ext/<name>/...`` from the extension's asset directory.

    Args:
        path: The parsed asset path; its first part is ``ext``.
        extension_assets: Extension name → resolved asset directory.

    Returns:
        ``(text, content_type)`` for a file inside the extension directory,
        otherwise ``None``.  The resolved candidate must stay inside the
        directory, so a symlink cannot escape it.
    """
    if len(path.parts) < 3:
        return None
    root = extension_assets.get(path.parts[1])
    if root is None:
        return None
    content_type = content_type_for(path.suffix)
    if content_type is None:
        return None

    resolved_root = Path(root).resolve()
    candidate = resolved_root.joinpath(*path.parts[2:]).resolve()
    if not candidate.is_relative_to(resolved_root) or not candidate.is_file():
        return None
    return candidate.read_text(encoding="utf-8"), content_type
