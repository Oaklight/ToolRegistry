"""Authentication module for admin panel.

This module provides simple token-based authentication for the admin panel,
using constant-time comparison to prevent timing attacks.
"""

import hashlib
import secrets
from http.server import BaseHTTPRequestHandler


class TokenAuth:
    """Simple token-based authentication.

    This class provides token generation and verification for securing
    the admin panel API endpoints.

    Attributes:
        token: The authentication token (read-only via property).

    Example:
        >>> auth = TokenAuth()  # Generate random token
        >>> print(f"Use token: {auth.token}")
        >>> auth.verify("some_token")  # Returns True/False
    """

    def __init__(self, token: str | None = None) -> None:
        """Initialize with optional token.

        If no token is provided, a cryptographically secure random token
        is generated.

        Args:
            token: Optional authentication token. If None, a random
                32-character hex token is generated.
        """
        if token is None:
            self._token = secrets.token_hex(16)  # 32 hex characters
        else:
            self._token = token

    @property
    def token(self) -> str:
        """Get the authentication token.

        Returns:
            The authentication token string.
        """
        return self._token

    def verify(self, provided_token: str) -> bool:
        """Verify a provided token using constant-time comparison.

        Uses HMAC-based comparison to prevent timing attacks.

        Args:
            provided_token: The token to verify.

        Returns:
            True if the token matches, False otherwise.
        """
        # Use constant-time comparison to prevent timing attacks
        expected_hash = hashlib.sha256(self._token.encode()).digest()
        provided_hash = hashlib.sha256(provided_token.encode()).digest()
        return secrets.compare_digest(expected_hash, provided_hash)

    def require_auth(self, handler: BaseHTTPRequestHandler) -> bool:
        """Check Authorization header and send 401 if invalid.

        Expects the Authorization header in the format:
        "Bearer <token>"

        Args:
            handler: The HTTP request handler to check and respond to.

        Returns:
            True if authentication is valid, False otherwise.
            If False, a 401 response has already been sent.
        """
        auth_header = handler.headers.get("Authorization", "")

        if not auth_header:
            self._send_unauthorized(handler, "Missing Authorization header")
            return False

        # Parse "Bearer <token>" format
        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            self._send_unauthorized(handler, "Invalid Authorization format")
            return False

        provided_token = parts[1]
        if not self.verify(provided_token):
            self._send_unauthorized(handler, "Invalid token")
            return False

        return True

    def _send_unauthorized(self, handler: BaseHTTPRequestHandler, message: str) -> None:
        """Send a 401 Unauthorized response.

        Args:
            handler: The HTTP request handler to send the response to.
            message: The error message to include in the response body.
        """
        handler.send_response(401)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("WWW-Authenticate", 'Bearer realm="admin"')
        handler.end_headers()
        import json

        response = json.dumps({"error": "Unauthorized", "message": message})
        handler.wfile.write(response.encode("utf-8"))
