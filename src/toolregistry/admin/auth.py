"""Authentication module for admin panel.

This module provides simple token-based authentication for the admin panel,
using constant-time comparison to prevent timing attacks.
"""

import hashlib
import secrets


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
