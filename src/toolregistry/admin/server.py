"""HTTP server for admin panel.

This module provides the AdminServer class for running the admin panel
as an async HTTP server in a background thread.
"""

import asyncio
import logging
import socket
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .._vendor.httpserver import App
from .auth import TokenAuth

if TYPE_CHECKING:
    from toolregistry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class AdminInfo:
    """Information about the running admin server.

    Attributes:
        host: The host address the server is bound to.
        port: The port number the server is listening on.
        url: The full URL to access the admin panel.
        token: The authentication token (if auth is enabled).
    """

    host: str
    port: int
    url: str
    token: str | None


class AdminApp(App):
    """App subclass with typed admin-specific attributes.

    Attributes:
        registry: The ToolRegistry instance to manage.
        auth: Optional TokenAuth instance for authentication.
        serve_ui: Whether to serve the admin UI at root path.
    """

    registry: "ToolRegistry"
    auth: TokenAuth | None
    serve_ui: bool


class AdminServer:
    """Admin panel HTTP server.

    This class manages an async HTTP server that provides a REST API and
    optional web UI for managing the ToolRegistry. The server runs in a
    background thread with its own asyncio event loop.

    Attributes:
        registry: The ToolRegistry instance to manage.
        host: The host address to bind to.
        port: The port number to listen on.
        serve_ui: Whether to serve the admin UI at root path.
        remote: Whether to allow remote connections.
        auth: The TokenAuth instance for authentication.

    Example:
        >>> from toolregistry import ToolRegistry
        >>> registry = ToolRegistry()
        >>> server = AdminServer(registry, port=8081)
        >>> info = server.start()
        >>> print(f"Admin panel at: {info.url}")
        >>> # ... later ...
        >>> server.stop()
    """

    def __init__(
        self,
        registry: "ToolRegistry",
        host: str = "127.0.0.1",
        port: int = 8081,
        serve_ui: bool = True,
        remote: bool = False,
        auth_token: str | None = None,
    ) -> None:
        """Initialize admin server.

        Args:
            registry: The ToolRegistry instance to manage.
            host: The host address to bind to. Defaults to "127.0.0.1".
            port: The port number to listen on. Defaults to 8081.
            serve_ui: Whether to serve the admin UI at root path. Defaults to True.
            remote: Whether to allow remote connections. If True, binds to "0.0.0.0".
                Defaults to False.
            auth_token: Optional authentication token. If None and remote is True,
                a random token is generated. If None and remote is False, no
                authentication is required.
        """
        self._registry = registry
        self._host = "0.0.0.0" if remote else host
        self._port = port
        self._serve_ui = serve_ui
        self._remote = remote

        # Set up authentication
        if auth_token is not None:
            self._auth: TokenAuth | None = TokenAuth(auth_token)
        elif remote:
            # Auto-generate token for remote access
            self._auth = TokenAuth()
        else:
            self._auth = None

        self._app: AdminApp | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()

    @property
    def registry(self) -> "ToolRegistry":
        """Get the managed ToolRegistry instance."""
        return self._registry

    @property
    def host(self) -> str:
        """Get the host address."""
        return self._host

    @property
    def port(self) -> int:
        """Get the port number."""
        return self._port

    @property
    def serve_ui(self) -> bool:
        """Get whether UI is served."""
        return self._serve_ui

    @property
    def auth(self) -> TokenAuth | None:
        """Get the authentication handler."""
        return self._auth

    def start(self) -> AdminInfo:
        """Start the server in a background thread.

        If the specified port is in use, automatically finds an available port.

        Returns:
            AdminInfo containing server details including URL and token.

        Raises:
            RuntimeError: If the server is already running.
        """
        if self._app is not None:
            raise RuntimeError("Server is already running")

        # Find available port
        actual_port = self.find_available_port(self._host, self._port)
        self._port = actual_port

        # Create app and attach context
        self._app = AdminApp()
        self._app.registry = self._registry
        self._app.auth = self._auth
        self._app.serve_ui = self._serve_ui

        # Register routes and middleware
        from .handlers import setup_routes

        setup_routes(self._app)

        # Start server in background thread
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

        # Wait for server to start
        self._started.wait(timeout=5.0)

        # Build URL
        display_host = (
            "localhost" if self._host in ("0.0.0.0", "127.0.0.1") else self._host
        )
        url = f"http://{display_host}:{self._port}"

        info = AdminInfo(
            host=self._host,
            port=self._port,
            url=url,
            token=self._auth.token if self._auth else None,
        )

        logger.info(f"Admin server started at {url}")
        if self._auth:
            logger.info(f"Authentication token: {self._auth.token}")

        return info

    def _run_server(self) -> None:
        """Run the async server in a background thread.

        Creates a new asyncio event loop and runs the server coroutine.
        The loop is cleaned up when the server shuts down.
        """
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_serve())
        finally:
            self._loop.close()
            self._loop = None

    async def _async_serve(self) -> None:
        """Async server coroutine.

        Replicates App._serve() logic but omits signal handler
        registration, which would fail in a non-main thread.
        """
        assert self._app is not None
        app = self._app
        app._shutdown_event = asyncio.Event()

        server = await asyncio.start_server(
            app._handle_connection,
            self._host,
            self._port,
        )

        app._server = server
        addrs = (
            server.sockets[0].getsockname()
            if server.sockets
            else (self._host, self._port)
        )
        app.host = addrs[0]
        app.port = addrs[1]

        # Signal that the server is ready
        self._started.set()

        async with server:
            await app._shutdown_event.wait()

    def stop(self) -> None:
        """Stop the server.

        This method is safe to call even if the server is not running.
        Uses ``loop.call_soon_threadsafe`` to safely trigger the asyncio
        shutdown event from the main thread.
        """
        if self._app is not None and self._loop is not None:
            if self._app._shutdown_event is not None:
                self._loop.call_soon_threadsafe(self._app._shutdown_event.set)

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

        self._app = None
        self._started.clear()
        logger.info("Admin server stopped")

    def is_running(self) -> bool:
        """Check if server is running.

        Returns:
            True if the server is running, False otherwise.
        """
        return self._app is not None and self._started.is_set()

    def get_info(self) -> AdminInfo | None:
        """Get server info if running.

        Returns:
            AdminInfo if server is running, None otherwise.
        """
        if not self.is_running():
            return None

        display_host = (
            "localhost" if self._host in ("0.0.0.0", "127.0.0.1") else self._host
        )
        url = f"http://{display_host}:{self._port}"

        return AdminInfo(
            host=self._host,
            port=self._port,
            url=url,
            token=self._auth.token if self._auth else None,
        )

    @staticmethod
    def find_available_port(host: str, start_port: int) -> int:
        """Find an available port starting from start_port.

        Tries ports sequentially until an available one is found.

        Args:
            host: The host address to check.
            start_port: The port number to start searching from.

        Returns:
            An available port number.

        Raises:
            RuntimeError: If no available port is found after 100 attempts.
        """
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind((host, port))
                    return port
            except OSError:
                continue

        raise RuntimeError(
            f"Could not find available port in range {start_port}-{start_port + 99}"
        )
