"""Authentication module for admin panel.

This module provides simple token-based authentication for the admin panel,
using constant-time comparison to prevent timing attacks.
"""

import collections
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable

#: Failed admin authentications a single client source may make inside
#: :data:`AUTH_FAILURE_WINDOW_SECONDS` before the panel answers 429.
AUTH_FAILURE_LIMIT = 5

#: Length of the sliding window over failed authentications, in seconds.
AUTH_FAILURE_WINDOW_SECONDS = 60.0

#: Maximum number of client sources tracked at once.  A remote address is
#: cheap to vary, so the table must not grow with the number of sources seen.
AUTH_FAILURE_MAX_SOURCES = 1024


class AuthFailureLimiter:
    """Sliding-window throttle over failed admin authentications.

    The admin token is a low-entropy shared secret when an operator supplies
    one by hand, so an unthrottled endpoint lets a client try candidates at
    the speed of the network.  This limiter records the time of each failed
    attempt per client source (the peer address) and reports the source as
    blocked once the window holds :data:`AUTH_FAILURE_LIMIT` failures.  A
    blocked request is answered with 429 before the token comparison runs.

    Memory is bounded.  At most ``max_sources`` sources are tracked: expired
    entries are pruned when a source is accessed, and the least recently used
    source is evicted when a new one would exceed the bound.  Only a bounded
    number of timestamps per source is kept, because older entries can no
    longer affect the decision.

    Args:
        limit: Failures inside *window* that block a source.
        window: Length of the sliding window, in seconds.
        max_sources: Maximum number of sources kept.
        clock: Monotonic clock, injectable for tests.

    Example:
        >>> limiter = AuthFailureLimiter()
        >>> limiter.retry_after("203.0.113.7") is None
        True
        >>> for _ in range(AUTH_FAILURE_LIMIT):
        ...     limiter.record_failure("203.0.113.7")
        >>> limiter.retry_after("203.0.113.7") is not None
        True
        >>> limiter.clear("203.0.113.7")
        >>> limiter.retry_after("203.0.113.7") is None
        True
    """

    def __init__(
        self,
        *,
        limit: int = AUTH_FAILURE_LIMIT,
        window: float = AUTH_FAILURE_WINDOW_SECONDS,
        max_sources: int = AUTH_FAILURE_MAX_SOURCES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window <= 0:
            raise ValueError("window must be positive")
        if max_sources < 1:
            raise ValueError("max_sources must be at least 1")
        self._limit = limit
        self._window = window
        self._max_sources = max_sources
        self._clock = clock
        self._failures: collections.OrderedDict[str, collections.deque[float]] = (
            collections.OrderedDict()
        )

    def retry_after(self, source: str) -> float | None:
        """Return the seconds *source* must wait, or ``None`` if it may try.

        Accessing a source prunes its expired failures, so a window that has
        passed always unblocks it.

        Args:
            source: Client source key, normally the peer address.

        Returns:
            Seconds until the oldest counted failure leaves the window, or
            ``None`` when the source is not blocked.
        """
        failures = self._failures.get(source)
        if failures is None:
            return None
        self._prune(source, failures)
        if not failures:
            return None
        self._failures.move_to_end(source)
        if len(failures) < self._limit:
            return None
        wait = failures[0] + self._window - self._clock()
        return wait if wait > 0 else None

    def record_failure(self, source: str) -> None:
        """Record one failed authentication for *source*.

        Args:
            source: Client source key, normally the peer address.
        """
        now = self._clock()
        failures = self._failures.get(source)
        if failures is None:
            if len(self._failures) >= self._max_sources:
                self._evict(now)
            failures = collections.deque()
            self._failures[source] = failures
        else:
            self._failures.move_to_end(source)
        failures.append(now)
        while len(failures) > self._limit:
            failures.popleft()

    def clear(self, source: str) -> None:
        """Forget the failures recorded for *source*, after a success.

        Args:
            source: Client source key, normally the peer address.
        """
        self._failures.pop(source, None)

    def _prune(self, source: str, failures: collections.deque[float]) -> None:
        """Drop timestamps that have left the window."""
        cutoff = self._clock() - self._window
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            self._failures.pop(source, None)

    def _evict(self, now: float) -> None:
        """Make room for one more source, preferring expired entries."""
        for source in list(self._failures):
            self._prune(source, self._failures[source])
        if len(self._failures) >= self._max_sources:
            self._failures.popitem(last=False)


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
        return hmac.compare_digest(expected_hash, provided_hash)


class SessionCookie:
    """HMAC-signed session cookies for browser-based admin access.

    Issues stateless session tokens: ``HMAC(secret, issued_at)`` +
    timestamp.  No server-side session store needed — verification
    re-computes the HMAC and checks expiry.

    The signed payload is the timestamp only — tokens are not bound
    to a specific client or IP.  This matches ``TokenAuth``'s
    shared-secret model where any holder of the token has access.

    A random secret is generated per server instance by default, so
    all sessions are invalidated on restart.  Pass an explicit
    *secret* for session persistence across restarts.

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
            A token string in the format ``timestamp.nonce.signature``.
        """
        ts = str(int(time.time()))
        nonce = secrets.token_hex(4)
        payload = f"{ts}.{nonce}"
        sig = self._sign(payload)
        return f"{payload}.{sig}"

    def verify(self, token: str) -> bool:
        """Verify a session token's signature and expiry.

        Args:
            token: The ``timestamp.nonce.signature`` token string.

        Returns:
            True if the signature is valid and the token has not expired.
        """
        parts = token.split(".", 2)
        if len(parts) != 3:
            return False
        ts_str, _nonce, sig = parts
        try:
            ts = int(ts_str)
        except ValueError:
            return False
        if time.time() - ts > self.max_age:
            return False
        payload = f"{ts_str}.{_nonce}"
        expected = self._sign(payload)
        return hmac.compare_digest(sig, expected)

    def _sign(self, data: str) -> str:
        """Compute HMAC-SHA256 of *data* with the secret."""
        return hmac.new(
            self._secret.encode(), data.encode(), hashlib.sha256
        ).hexdigest()
