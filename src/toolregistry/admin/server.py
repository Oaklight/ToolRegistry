"""HTTP server for admin panel.

This module provides the AdminServer class for running the admin panel
as an async HTTP server in a background thread.
"""

import asyncio
import logging
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .._vendor.httpserver import App
from .auth import SessionCookie, TokenAuth
from .metrics import RequestMetrics

if TYPE_CHECKING:
    from toolregistry import ToolRegistry
    from toolregistry.config import ToolConfig

logger = logging.getLogger(__name__)


@dataclass
class AdminInfo:
    """Information about the running admin server.

    Attributes:
        host: The host address the server is bound to.
        port: The port number the server is listening on.
        url: The full URL to access the admin panel.
        token: The authentication token (if auth is enabled).
        secure: Whether the server is serving over TLS.
    """

    host: str
    port: int
    url: str
    token: str | None
    secure: bool = False


class AdminApp(App):
    """App subclass with typed admin-specific attributes.

    Attributes:
        registry: The ToolRegistry instance to manage.
        auth: Optional TokenAuth instance for authentication.
        session: Optional SessionCookie for browser cookie auth.
        serve_ui: Whether to serve the admin UI at root path.
        config: Optional ToolConfig for config-aware endpoints.
        metrics: HTTP request metrics collected from lifecycle signals.
    """

    registry: "ToolRegistry"
    auth: TokenAuth | None
    session: SessionCookie | None
    serve_ui: bool
    config: "ToolConfig | None"
    metrics: RequestMetrics | None = None


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

    #: Seconds to wait for the listener to signal readiness.
    _START_TIMEOUT_SECONDS = 5.0

    def __init__(
        self,
        registry: "ToolRegistry",
        host: str = "127.0.0.1",
        port: int = 8081,
        serve_ui: bool = True,
        remote: bool = False,
        auth_token: str | None = None,
        session_secret: str | None = None,
        config: "ToolConfig | None" = None,
        ssl_context: ssl.SSLContext | None = None,
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
            session_secret: Optional secret for signing session cookies.
                When None, a random secret is generated per server instance
                (sessions invalidated on restart).  Pass an explicit value
                for session persistence across restarts.
            config: Optional ToolConfig for config-aware admin endpoints.
                When provided, enables ``GET /api/config`` and
                ``PUT /api/config`` endpoints for viewing and persisting
                configuration changes.
            ssl_context: Optional :class:`ssl.SSLContext` for TLS termination.
                When provided, the admin server accepts HTTPS connections.
                The caller is responsible for configuring the context
                (certificate chain, verification mode, etc.).
        """
        self._registry = registry
        self._host = "0.0.0.0" if remote else host
        self._port = port
        self._serve_ui = serve_ui
        self._remote = remote
        self._config = config
        self._ssl_context = ssl_context

        # Set up authentication
        if auth_token is not None:
            self._auth: TokenAuth | None = TokenAuth(auth_token)
        elif remote:
            # Auto-generate token for remote access
            self._auth = TokenAuth()
        else:
            self._auth = None

        self._session: SessionCookie | None = (
            SessionCookie(secret=session_secret) if self._auth is not None else None
        )

        self._app: AdminApp | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._start_failed = threading.Event()
        self._start_error: BaseException | None = None

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

    @property
    def ssl_context(self) -> ssl.SSLContext | None:
        """Get the TLS context, if one was configured."""
        return self._ssl_context

    @property
    def metrics(self) -> RequestMetrics | None:
        """Get the running server's request metrics, if available."""
        return self._app.metrics if self._app is not None else None

    def _base_url(self) -> str:
        """Build the externally visible base URL."""
        display_host = (
            "localhost" if self._host in ("0.0.0.0", "127.0.0.1") else self._host
        )
        scheme = "https" if self._ssl_context is not None else "http"
        return f"{scheme}://{display_host}:{self._port}"

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

        self._started.clear()
        self._start_failed.clear()
        self._start_error = None

        # Find available port
        actual_port = self.find_available_port(self._host, self._port)
        self._port = actual_port

        # Create app and attach context
        self._app = AdminApp()
        self._app.registry = self._registry
        self._app.auth = self._auth
        self._app.session = self._session
        self._app.serve_ui = self._serve_ui
        self._app.config = self._config

        # Collect HTTP metrics from the lifecycle signals.  Register the
        # timing hook before setup_routes so it runs before CORS/auth and
        # still sees short-circuited requests.
        self._app.metrics = RequestMetrics()
        self._app.before_request(self._app.metrics.before_request)

        # Register routes and middleware
        from .handlers import setup_routes

        setup_routes(self._app)
        self._app.on_response_started(self._app.metrics.response_started)
        self._app.on_response_completed(self._app.metrics.response_completed)
        self._app.on_client_disconnect(self._app.metrics.client_disconnect)

        # Start server in background thread
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

        # Wait for the listener to signal readiness, or for startup to fail.
        deadline = time.monotonic() + self._START_TIMEOUT_SECONDS
        while not self._started.is_set():
            if self._start_failed.is_set():
                self._app = None
                self._thread = None
                raise RuntimeError(
                    "Admin server failed to start"
                ) from self._start_error
            if time.monotonic() >= deadline:
                self._abort_start()
                raise RuntimeError(
                    "Admin server did not start within "
                    f"{self._START_TIMEOUT_SECONDS:g} seconds"
                ) from self._start_error
            time.sleep(0.01)

        # A port of 0 lets the OS pick an ephemeral port; record the actual
        # bound port so AdminInfo.url points at the listener.
        assert self._app is not None
        assert self._app.port is not None
        self._port = self._app.port

        # Build URL
        url = self._base_url()

        info = AdminInfo(
            host=self._host,
            port=self._port,
            url=url,
            token=self._auth.token if self._auth else None,
            secure=self._ssl_context is not None,
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
        except Exception as exc:
            self._start_error = exc
            self._start_failed.set()
            logger.debug("Admin server startup failed", exc_info=True)
        finally:
            self._loop.close()
            self._loop = None

    def _abort_start(self) -> None:
        """Stop a server that never signalled readiness.

        The shutdown event is set through the server loop, then the thread is
        joined.  References are only cleared once the thread has exited, so a
        listener that binds late can still be shut down by ``stop()``.
        """
        loop = self._loop
        app = self._app
        if loop is not None and app is not None:
            event = app._shutdown_event
            if event is not None:
                try:
                    loop.call_soon_threadsafe(event.set)
                except RuntimeError:
                    pass

        thread = self._thread
        if thread is not None:
            thread.join(timeout=self._START_TIMEOUT_SECONDS)
            if not thread.is_alive():
                self._thread = None
                self._app = None
        self._started.clear()

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
            ssl=self._ssl_context,
        )

        app._server = server
        addrs = (
            server.sockets[0].getsockname()
            if server.sockets
            else (self._host, self._port)
        )
        app.host = addrs[0]
        app.port = addrs[1]

        if self._ssl_context is not None and server.sockets:
            await self._verify_tls_handshake(server)

        # Signal that the server is ready
        self._started.set()

        async with server:
            await app._shutdown_event.wait()

    async def _verify_tls_handshake(self, server: asyncio.Server) -> None:
        """Complete a loopback handshake to validate the TLS context.

        ``asyncio.start_server`` accepts a context that cannot serve TLS
        (for example one with no certificate chain).  Such a listener binds
        and looks healthy but fails every client handshake, so verify it
        once on loopback before reporting the server as ready.
        """
        assert server.sockets
        address = server.sockets[0].getsockname()
        host = address[0]
        if host in ("", "0.0.0.0"):
            host = "127.0.0.1"
        elif host == "::":
            host = "::1"

        client_context = ssl.create_default_context()
        client_context.check_hostname = False
        client_context.verify_mode = ssl.CERT_NONE

        try:
            _, writer = await asyncio.open_connection(
                host,
                address[1],
                ssl=client_context,
                server_hostname=None,
            )
        except Exception as exc:
            server.close()
            await server.wait_closed()
            raise RuntimeError(
                "TLS handshake failed with the configured ssl_context"
            ) from exc

        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

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
            self._thread.join(timeout=self._START_TIMEOUT_SECONDS)
            if self._thread.is_alive():
                logger.warning(
                    "Admin server thread did not stop within %g seconds; "
                    "call stop() again to retry",
                    self._START_TIMEOUT_SECONDS,
                )
                return
            self._thread = None

        self._app = None
        self._started.clear()
        self._start_failed.clear()
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

        return AdminInfo(
            host=self._host,
            port=self._port,
            url=self._base_url(),
            token=self._auth.token if self._auth else None,
            secure=self._ssl_context is not None,
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
