"""Admin panel mixin for ToolRegistry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..admin import AdminExtension, AdminInfo, AdminServer, SourcePersistenceHook
    from ..config import ToolConfig
    from ..tool_registry import ToolRegistry


class AdminMixin:
    """Mixin providing admin panel management."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._admin_server: AdminServer | None = None

    def enable_admin(
        self,
        host: str = "127.0.0.1",
        port: int = 8081,
        serve_ui: bool = True,
        remote: bool = False,
        auth_token: str | None = None,
        config: ToolConfig | None = None,
        allow_private_hosts: bool = False,
        extensions: Iterable[AdminExtension] | None = None,
        source_hook: SourcePersistenceHook | None = None,
        trusted_proxies: Sequence[str] = (),
    ) -> AdminInfo:
        """Enable the admin panel.

        Starts an HTTP server that provides a REST API and optional web UI
        for managing the registry.

        Args:
            host: The host address to bind to. Defaults to "127.0.0.1".
            port: The port number to listen on. Defaults to 8081.
            serve_ui: Whether to serve the admin UI at root path. Defaults to True.
            remote: Whether to allow remote connections. If True, binds to "0.0.0.0"
                and auto-generates an auth token if none provided. Defaults to False.
            auth_token: Optional authentication token. If None and remote is True,
                a random token is generated.
            config: Optional ToolConfig for config-aware admin endpoints.
                When provided, enables ``GET /api/config`` and
                ``PUT /api/config`` endpoints for viewing and persisting
                configuration changes to the source file.
            allow_private_hosts: Let the panel fetch a spec or a server URL
                that resolves to a loopback, link-local or private address.
                Defaults to ``False``; set it to register an API on the same
                host or a private network.
            extensions: Admin panel extensions to mount.  Each one is
                validated before the listener starts; a contract violation
                raises ``AdminExtensionError`` naming the extension.
                Defaults to no extensions.
            source_hook: Optional persistence and status hook for tool
                sources.  The panel hands every registered source to it and
                exposes its records in ``GET /api/sources``.  Defaults to
                none: nothing is persisted and the response shapes are
                unchanged.
            trusted_proxies: Addresses or CIDR ranges of reverse proxies
                whose ``X-Forwarded-For`` header is trusted for the
                authentication throttle key.  Empty keeps the peer
                address as the key; see :class:`~toolregistry.admin.AdminServer`.

        Returns:
            AdminInfo containing server details including URL and token.

        Raises:
            RuntimeError: If the admin panel is already running.

        Example:
            ```python
            registry = ToolRegistry()
            info = registry.enable_admin(port=8081)
            print(f"Admin panel at: {info.url}")
            if info.token:
                print(f"Token: {info.token}")
            ```
        """
        if self._admin_server is not None and self._admin_server.is_running():
            raise RuntimeError("Admin panel is already running")

        from typing import cast

        from ..admin import AdminServer

        self._admin_server = AdminServer(
            registry=cast("ToolRegistry", self),
            host=host,
            port=port,
            serve_ui=serve_ui,
            remote=remote,
            auth_token=auth_token,
            config=config,
            allow_private_hosts=allow_private_hosts,
            extensions=extensions,
            source_hook=source_hook,
            trusted_proxies=trusted_proxies,
        )
        return self._admin_server.start()

    def disable_admin(self) -> None:
        """Disable the admin panel.

        Stops the admin HTTP server if it is running.
        This method is safe to call even if the admin panel is not running.

        Example:
            ```python
            registry.disable_admin()
            ```
        """
        if self._admin_server is not None:
            self._admin_server.stop()
            self._admin_server = None

    def get_admin_info(self) -> AdminInfo | None:
        """Get admin panel info if running.

        Returns:
            AdminInfo if the admin panel is running, None otherwise.

        Example:
            ```python
            info = registry.get_admin_info()
            if info:
                print(f"Admin panel running at: {info.url}")
            ```
        """
        if self._admin_server is None:
            return None
        return self._admin_server.get_info()
