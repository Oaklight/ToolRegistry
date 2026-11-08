"""Extension contract for the admin panel.

An extension contributes a navigation section to the panel, one asset
directory, and optionally HTTP routes under ``/ext/<name>``.  The host keeps
ownership of authentication, the shell, and the asset path; an extension does
not touch them.

The contract is versioned by :data:`ADMIN_EXTENSION_API`.  Every extension
declares the version it targets in ``requires_api``, and the server refuses to
start when that differs from the host's, naming the extension in the error.
This keeps a future contract change from silently breaking an extension that
was written for an older host.

Example:
    >>> class ClockExt:
    ...     name = "clock"
    ...     title = {"en": "Clock", "zh": "时钟"}
    ...     entry = "assets/ext/clock/main.js"
    ...     requires_api = ADMIN_EXTENSION_API
    ...     assets = Path("/srv/ext/clock/static")
    ...
    ...     def register(self, ctx):
    ...         ctx.get("/now", self.now)
    ...
    ...     def now(self, request):
    ...         return {"now": time.time()}
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

from .static import content_type_for

if TYPE_CHECKING:
    from toolregistry import ToolRegistry

    from .server import AdminApp

#: Version of the extension contract implemented by this host.
ADMIN_EXTENSION_API = 1

#: URL prefix every extension route lives under.
EXTENSION_PREFIX = "/ext"

#: URL prefix every extension asset lives under (relative to the panel root).
EXTENSION_ASSET_PREFIX = "assets/ext"

#: Extension names become a URL segment and a filesystem lookup key, so the
#: charset is deliberately narrow.
_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

#: HTTP methods :class:`AdminContext` can register.
_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

#: Default navigation order when an extension does not set one.
DEFAULT_NAV_ORDER = 100


class AdminExtensionError(RuntimeError):
    """An extension does not satisfy the admin extension contract."""


@runtime_checkable
class AdminExtension(Protocol):
    """Structural contract for an admin panel extension.

    Only the members below are required.  The host reads the remaining
    members with a default when they are absent:

    Attributes:
        name: Lower-case identifier matching ``^[a-z][a-z0-9_-]*$``.  It is
            the URL segment (``/ext/<name>``) and the key of the asset
            directory.
        title: Locale map used as the navigation label, for example
            ``{"en": "Clock", "zh": "时钟"}``.  The loader uses the active
            language, then ``en``, then any value.
        entry: Browser module path under ``assets/ext/<name>/``.  It exports
            ``register({container, api, i18n})`` and optionally ``unmount()``.
        requires_api: Contract version the extension was written for.  Must
            equal :data:`ADMIN_EXTENSION_API`.
        register: Called once with an :class:`AdminContext`.  It registers the
            extension's HTTP routes and returns.
    """

    @property
    def name(self) -> str:
        """Lower-case identifier used as the URL segment."""

    @property
    def title(self) -> Mapping[str, str]:
        """Locale -> navigation label."""

    @property
    def entry(self) -> str:
        """Browser module path under ``assets/ext/<name>/``."""

    @property
    def requires_api(self) -> int:
        """Contract version the extension targets."""

    def register(self, ctx: AdminContext) -> None:
        """Register routes on *ctx*."""


def _normalize_subpath(path: str) -> str:
    """Validate an extension-relative path and return it canonicalised.

    Args:
        path: A route or asset path relative to the extension prefix.  An
            empty string and ``"/"`` both mean the prefix itself.

    Returns:
        The path with a leading slash, or ``""`` for the prefix itself.

    Raises:
        AdminExtensionError: If *path* is not a plain absolute-style path.
            Query strings, fragments, backslashes and dot segments are
            rejected: they would either bypass the prefix or address a file
            outside the extension's asset directory.
    """
    if not isinstance(path, str):
        raise AdminExtensionError(f"path must be a string, got {type(path).__name__}")
    if path in ("", "/"):
        return ""
    if not path.startswith("/"):
        raise AdminExtensionError(f"path must start with '/', got {path!r}")
    if "\\" in path or "?" in path or "#" in path:
        raise AdminExtensionError(f"path must not contain '\\', '?' or '#': {path!r}")
    if any(part in ("..", ".") for part in PurePosixPath(path).parts):
        raise AdminExtensionError(f"path must not contain dot segments: {path!r}")
    return path


class AdminContext:
    """Registration handle an extension receives in ``register``.

    The context is bound to one extension.  Routes are relative to
    ``/ext/<name>`` and assets to ``assets/ext/<name>/``, so an extension
    cannot address another one's namespace.

    Attributes:
        name: The extension name this context belongs to.
        registry: The registry the panel manages.
    """

    def __init__(self, app: AdminApp, name: str, assets_dir: Path) -> None:
        self._app = app
        self._name = name
        self._assets_dir = assets_dir
        self._routes: set[tuple[str, str]] = set()

    @property
    def name(self) -> str:
        """The extension name."""
        return self._name

    @property
    def registry(self) -> ToolRegistry:
        """The registry the admin panel manages."""
        return self._app.registry

    @property
    def api_prefix(self) -> str:
        """URL prefix of every route registered through this context."""
        return f"{EXTENSION_PREFIX}/{self._name}"

    @property
    def asset_prefix(self) -> str:
        """URL prefix of the extension's asset directory."""
        return f"/{EXTENSION_ASSET_PREFIX}/{self._name}"

    def api_url(self, path: str = "") -> str:
        """Return the absolute URL of a route registered on this context.

        Args:
            path: Route path relative to :attr:`api_prefix`.

        Returns:
            The URL path, with the prefix applied.
        """
        return self.api_prefix + _normalize_subpath(path)

    def asset_url(self, path: str = "") -> str:
        """Return the absolute URL of a file in the extension's assets.

        Args:
            path: File path relative to the asset directory.

        Returns:
            The URL path, with the asset prefix applied.
        """
        return self.asset_prefix + _normalize_subpath(path)

    def get(self, path: str, handler: Callable[..., Any] | None = None) -> Any:
        """Register a ``GET`` route, as a call or as a decorator."""
        return self._route("GET", path, handler)

    def post(self, path: str, handler: Callable[..., Any] | None = None) -> Any:
        """Register a ``POST`` route, as a call or as a decorator."""
        return self._route("POST", path, handler)

    def put(self, path: str, handler: Callable[..., Any] | None = None) -> Any:
        """Register a ``PUT`` route, as a call or as a decorator."""
        return self._route("PUT", path, handler)

    def patch(self, path: str, handler: Callable[..., Any] | None = None) -> Any:
        """Register a ``PATCH`` route, as a call or as a decorator."""
        return self._route("PATCH", path, handler)

    def delete(self, path: str, handler: Callable[..., Any] | None = None) -> Any:
        """Register a ``DELETE`` route, as a call or as a decorator."""
        return self._route("DELETE", path, handler)

    def _route(
        self,
        method: str,
        path: str,
        handler: Callable[..., Any] | None,
    ) -> Any:
        """Register *handler* for *method* at *path*, or return a decorator."""
        if method not in _METHODS:  # pragma: no cover - internal call sites
            raise AdminExtensionError(f"unsupported method {method!r}")

        def register(target: Callable[..., Any]) -> Callable[..., Any]:
            if not callable(target):
                raise AdminExtensionError(
                    f"extension '{self._name}' registered a non-callable handler "
                    f"for {method} {path!r}"
                )
            full = self.api_prefix + _normalize_subpath(path)
            key = (method, full)
            if key in self._routes:
                raise AdminExtensionError(
                    f"extension '{self._name}' already registered {method} {full}"
                )
            self._routes.add(key)
            self._app.route(full, methods=[method])(target)
            return target

        if handler is None:
            return register
        return register(handler)


@dataclass(frozen=True)
class MountedExtension:
    """A validated extension, ready to advertise in the manifest.

    Attributes:
        name: Extension identifier.
        title: Locale → label map.
        icon: Optional SVG markup for the navigation item.
        nav_group: Optional console group label.  Extensions that share a
            group are listed together.
        nav_order: Sort key inside the group.
        entry: Module path under ``assets/ext/<name>/``.
        styles: Stylesheet paths under ``assets/ext/<name>/``.
        assets_dir: Resolved directory the asset paths read from.
    """

    name: str
    title: dict[str, str]
    icon: str | None
    nav_group: str | None
    nav_order: int
    entry: str
    styles: tuple[str, ...]
    assets_dir: Path

    @property
    def api_prefix(self) -> str:
        """URL prefix of the extension's routes."""
        return f"{EXTENSION_PREFIX}/{self.name}"

    def manifest(self) -> dict[str, Any]:
        """Return the public description served by ``GET /api/extensions``.

        Returns:
            A JSON-serialisable mapping with the contract fields.  Optional
            fields are present with their defaults so a client does not have
            to test for absence.
        """
        return {
            "name": self.name,
            "title": dict(self.title),
            "icon": self.icon,
            "nav": {"group": self.nav_group, "order": self.nav_order},
            "entry": self.entry,
            "styles": list(self.styles),
            "api_prefix": self.api_prefix,
            "requires_api": ADMIN_EXTENSION_API,
        }


def _require_name(extension: object) -> str:
    """Return the extension's validated name."""
    name = getattr(extension, "name", None)
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise AdminExtensionError(
            f"extension name {name!r} must match {_NAME_RE.pattern}"
        )
    return name


def _require_title(extension: object, name: str) -> dict[str, str]:
    """Return the extension's validated locale map."""
    title = getattr(extension, "title", None)
    if not isinstance(title, Mapping) or not title:
        raise AdminExtensionError(
            f"extension '{name}' must provide a non-empty title mapping"
        )
    normalized: dict[str, str] = {}
    for locale, label in title.items():
        if not isinstance(locale, str) or not locale:
            raise AdminExtensionError(
                f"extension '{name}' has a non-string title locale: {locale!r}"
            )
        if not isinstance(label, str) or not label:
            raise AdminExtensionError(
                f"extension '{name}' has an empty title for locale '{locale}'"
            )
        normalized[locale] = label
    return normalized


def _require_assets_dir(extension: object, name: str) -> Path:
    """Return the extension's resolved asset directory."""
    raw = getattr(extension, "assets", None)
    if raw is None:
        raise AdminExtensionError(
            f"extension '{name}' must provide an assets directory"
        )
    try:
        assets_dir = Path(raw).resolve()
    except TypeError as exc:
        raise AdminExtensionError(
            f"extension '{name}' has an invalid assets directory: {raw!r}"
        ) from exc
    if not assets_dir.is_dir():
        raise AdminExtensionError(
            f"extension '{name}' assets directory does not exist: {assets_dir}"
        )
    return assets_dir


def _require_asset_path(value: object, name: str, assets_dir: Path, field: str) -> str:
    """Validate one declared asset path and return it as an ``assets/`` URL.

    Args:
        value: The declared path, for example ``assets/ext/clock/main.js``.
        name: The extension name that must own the path.
        assets_dir: Directory the path is served from.
        field: Field name used in error messages.

    Returns:
        The URL path, with the ``assets/`` prefix applied.

    Raises:
        AdminExtensionError: If the path is malformed, outside the extension's
            asset prefix, unsupported by the suffix whitelist, or does not
            name a file inside *assets_dir*.
    """
    if not isinstance(value, str) or not value:
        raise AdminExtensionError(
            f"extension '{name}' {field} must be a non-empty string"
        )
    if "\\" in value or value.startswith("/"):
        raise AdminExtensionError(
            f"extension '{name}' {field} must be a relative path: {value!r}"
        )
    path = PurePosixPath(value)
    if any(part in ("..", ".") for part in path.parts):
        raise AdminExtensionError(
            f"extension '{name}' {field} must not contain dot segments: {value!r}"
        )
    if path.parts[:2] != ("ext", name) or len(path.parts) < 3:
        raise AdminExtensionError(
            f"extension '{name}' {field} must start with "
            f"'{EXTENSION_ASSET_PREFIX}/{name}/': {value!r}"
        )
    if content_type_for(path.suffix) is None:
        raise AdminExtensionError(
            f"extension '{name}' {field} has an unsupported file type: {value!r}"
        )

    candidate = assets_dir.joinpath(*path.parts[2:])
    try:
        resolved = candidate.resolve()
    except OSError as exc:  # pragma: no cover - unusual filesystem state
        raise AdminExtensionError(
            f"extension '{name}' {field} cannot be resolved: {value!r}"
        ) from exc
    if not resolved.is_relative_to(assets_dir):
        raise AdminExtensionError(
            f"extension '{name}' {field} leaves the assets directory: {value!r}"
        )
    if not resolved.is_file():
        raise AdminExtensionError(
            f"extension '{name}' {field} does not exist: {value!r}"
        )
    return f"{EXTENSION_ASSET_PREFIX}/{value.removeprefix('ext/')}"


def _require_nav(extension: object, name: str) -> tuple[str | None, int]:
    """Return the validated ``nav`` group and order."""
    nav = getattr(extension, "nav", None)
    if nav is None:
        return None, DEFAULT_NAV_ORDER
    if not isinstance(nav, Mapping):
        raise AdminExtensionError(f"extension '{name}' nav must be a mapping")
    unknown = set(nav) - {"group", "order"}
    if unknown:
        raise AdminExtensionError(
            f"extension '{name}' nav has unknown keys: {sorted(map(str, unknown))}"
        )
    group = nav.get("group")
    if group is not None and (not isinstance(group, str) or not group):
        raise AdminExtensionError(
            f"extension '{name}' nav group must be a non-empty string"
        )
    order = nav.get("order", DEFAULT_NAV_ORDER)
    if isinstance(order, bool) or not isinstance(order, int):
        raise AdminExtensionError(
            f"extension '{name}' nav order must be an integer, got {order!r}"
        )
    return group, order


def _prepare_one(extension: object) -> MountedExtension:
    """Validate one extension and return its mounted description."""
    name = _require_name(extension)
    requires_api = getattr(extension, "requires_api", None)
    if requires_api != ADMIN_EXTENSION_API:
        raise AdminExtensionError(
            f"extension '{name}' requires admin extension API "
            f"{requires_api!r}; this host provides {ADMIN_EXTENSION_API}"
        )
    register = getattr(extension, "register", None)
    if not callable(register):
        raise AdminExtensionError(
            f"extension '{name}' must define a register(context) method"
        )
    title = _require_title(extension, name)
    assets_dir = _require_assets_dir(extension, name)
    entry = _require_asset_path(
        getattr(extension, "entry", None), name, assets_dir, "entry"
    )

    styles_raw = getattr(extension, "styles", None) or ()
    if isinstance(styles_raw, str) or not isinstance(styles_raw, Sequence):
        raise AdminExtensionError(
            f"extension '{name}' styles must be a sequence of asset paths"
        )
    styles = tuple(
        _require_asset_path(value, name, assets_dir, "style") for value in styles_raw
    )

    icon = getattr(extension, "icon", None)
    if icon is not None and not isinstance(icon, str):
        raise AdminExtensionError(f"extension '{name}' icon must be a string")
    group, order = _require_nav(extension, name)

    return MountedExtension(
        name=name,
        title=title,
        icon=icon,
        nav_group=group,
        nav_order=order,
        entry=entry,
        styles=styles,
        assets_dir=assets_dir,
    )


def prepare_extensions(extensions: Iterable[object] | None) -> tuple[object, ...]:
    """Validate *extensions* without touching an app.

    Args:
        extensions: Extension instances, or ``None``.

    Returns:
        The same extensions as a tuple, so callers can iterate twice.

    Raises:
        AdminExtensionError: If an extension breaks the contract or two share
            a name.
    """
    if extensions is None:
        return ()
    prepared = tuple(extensions)
    seen: set[str] = set()
    for extension in prepared:
        name = _require_name(extension)
        if name in seen:
            raise AdminExtensionError(f"duplicate extension name '{name}'")
        seen.add(name)
        _prepare_one(extension)
    return prepared


def mount_extensions(
    app: AdminApp, extensions: Iterable[object] | None
) -> tuple[MountedExtension, ...]:
    """Validate *extensions* and register their routes on *app*.

    The app is left untouched when validation fails; callers should discard it
    rather than serve a partially mounted panel.

    Args:
        app: The admin application the routes belong to.
        extensions: Extension instances, or ``None``.

    Returns:
        The mounted extensions in declaration order.

    Raises:
        AdminExtensionError: If an extension breaks the contract, two share a
            name, or ``register`` raises.  The message always names the
            extension.
    """
    instances = prepare_extensions(extensions)
    mounted: list[MountedExtension] = []
    for extension in instances:
        info = _prepare_one(extension)
        context = AdminContext(app, info.name, info.assets_dir)
        try:
            cast(AdminExtension, extension).register(context)
        except AdminExtensionError as exc:
            if f"'{info.name}'" in str(exc):
                raise
            raise AdminExtensionError(f"extension '{info.name}': {exc}") from exc
        except Exception as exc:
            raise AdminExtensionError(
                f"extension '{info.name}' failed to register: {exc}"
            ) from exc
        mounted.append(info)

    app.extensions = tuple(mounted)
    app.extension_assets = {info.name: info.assets_dir for info in mounted}
    return tuple(mounted)
