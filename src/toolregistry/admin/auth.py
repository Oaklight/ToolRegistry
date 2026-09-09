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


class SessionCookie:
    """HMAC-signed session cookies for browser-based admin access.

    Issues stateless session tokens: ``HMAC(secret, issued_at)`` +
    timestamp.  No server-side session store needed — verification
    re-computes the HMAC and checks expiry.

    Args:
        secret: Signing secret.  Defaults to a random 32-byte hex string.
        max_age: Session lifetime in seconds.  Default is 3600 (1 hour).
        cookie_name: Name of the session cookie.
    """

    def __init__(
        self,
        secret: str | None = None,
        max_age: int = 3600,
        cookie_name: str = "tr_session",
    ) -> None:
        self._secret = secret or secrets.token_hex(32)
        self.max_age = max_age
        self.cookie_name = cookie_name

    def issue(self) -> str:
        """Create a signed session token.

        Returns:
            A token string in the format ``timestamp.signature``.
        """
        import time

        ts = str(int(time.time()))
        sig = self._sign(ts)
        return f"{ts}.{sig}"

    def verify(self, token: str) -> bool:
        """Verify a session token's signature and expiry.

        Args:
            token: The ``timestamp.signature`` token string.

        Returns:
            True if the signature is valid and the token has not expired.
        """
        import time

        parts = token.split(".", 1)
        if len(parts) != 2:
            return False
        ts_str, sig = parts
        try:
            ts = int(ts_str)
        except ValueError:
            return False
        if time.time() - ts > self.max_age:
            return False
        expected = self._sign(ts_str)
        return secrets.compare_digest(sig, expected)

    def _sign(self, data: str) -> str:
        """Compute HMAC-SHA256 of *data* with the secret."""
        import hmac

        return hmac.new(
            self._secret.encode(), data.encode(), hashlib.sha256
        ).hexdigest()
