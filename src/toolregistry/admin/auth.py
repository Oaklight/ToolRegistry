"""Authentication module for admin panel.

This module provides simple token-based authentication for the admin panel,
using constant-time comparison to prevent timing attacks.
"""

import collections
import dataclasses
import hashlib
import hmac
import ipaddress
import secrets
import threading
import time
from collections.abc import Callable, Sequence

#: Failed admin authentications a single client source may make inside
#: :data:`AUTH_FAILURE_WINDOW_SECONDS` before the panel answers 429.
AUTH_FAILURE_LIMIT = 5

#: Length of the sliding window over failed authentications, in seconds.
AUTH_FAILURE_WINDOW_SECONDS = 60.0

#: Maximum number of client sources tracked at once.  A remote address is
#: cheap to vary, so the table must not grow with the number of sources seen.
AUTH_FAILURE_MAX_SOURCES = 1024

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_trusted_proxies(entries: Sequence[str]) -> tuple[IPNetwork, ...]:
    """Parse the addresses or CIDR ranges a reverse proxy connects from.

    Args:
        entries: Exact addresses (``"127.0.0.1"``) or CIDR ranges
            (``"127.0.0.0/8"``).  A bare address is treated as a single-host
            range.

    Returns:
        The parsed networks, in the order given.

    Raises:
        ValueError: If an entry is not an IP address or CIDR range.
    """
    networks: list[IPNetwork] = []
    for entry in entries:
        try:
            networks.append(ipaddress.ip_network(entry.strip(), strict=False))
        except ValueError as exc:
            raise ValueError(
                f"trusted proxy {entry!r} is not an IP address or CIDR range"
            ) from exc
    return tuple(networks)


def normalize_address(address: str) -> str | None:
    """Return the canonical text form of *address*, or ``None`` if invalid.

    An IPv4-mapped IPv6 address (``::ffff:127.0.0.1``) is reported as its
    IPv4 form.  A dual-stack listener reports IPv4 peers that way, and the
    throttle key must not depend on which listener accepted the connection.

    Args:
        address: An IPv4 or IPv6 address in text form.

    Returns:
        The canonical address, with mapped IPv6 addresses reduced to IPv4,
        or ``None`` when *address* does not parse.
    """
    try:
        parsed = ipaddress.ip_address(address.strip())
    except ValueError:
        return None
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        return str(parsed.ipv4_mapped)
    return str(parsed)


def address_in_networks(address: str, networks: Sequence[IPNetwork]) -> bool:
    """Return whether *address* belongs to any of *networks*.

    The address is normalized first, so an IPv4-mapped IPv6 address matches
    the IPv4 networks it represents.
    """
    normalized = normalize_address(address)
    if normalized is None:
        return False
    parsed = ipaddress.ip_address(normalized)
    return any(
        parsed.version == network.version and parsed in network for network in networks
    )


def forwarded_source(header: str, trusted: Sequence[IPNetwork]) -> str | None:
    """Return the client address from an ``X-Forwarded-For`` chain.

    The chain is walked right to left, skipping hops that are themselves
    trusted; the first untrusted address is the client.  That is the only
    order a client cannot steer by prepending entries, because the trusted
    proxy appends the hop it actually saw.  Addresses are normalized, so an
    IPv4-mapped hop matches an IPv4 trusted network and yields the IPv4 key.

    Args:
        header: The raw header value, possibly empty.
        trusted: Networks whose addresses are skipped.

    Returns:
        The client address, or ``None`` when the chain is empty, when a hop
        at or right of the client does not parse, or when every hop is
        trusted.  The caller falls back to the peer address in that case.
        Hops left of the returned client are never examined: the client can
        forge them, and the trusted proxy appends its own view to their
        right, so they cannot affect the key.
    """
    entries = [part.strip() for part in header.split(",") if part.strip()]
    if not entries:
        return None
    for entry in reversed(entries):
        address = normalize_address(entry)
        if address is None:
            # A malformed hop at or right of the client position makes the
            # chain untrustworthy.  Hops further left are the client's own
            # forging space and are never reached.
            return None
        if not address_in_networks(address, trusted):
            return address
    return None


@dataclasses.dataclass(frozen=True, slots=True)
class AuthAttempt:
    """One reserved authentication attempt.

    Attributes:
        source: Client source key the attempt was reserved for.
        sequence: Reservation order.  A success releases this attempt and
            the failures that preceded it, but not failures reserved later.
    """

    source: str
    sequence: int


class AuthFailureLimiter:
    """Sliding-window throttle over failed admin authentications.

    The admin token is a low-entropy shared secret when an operator supplies
    one by hand, so an unthrottled endpoint lets a client try candidates at
    the speed of the network.  This limiter reserves one slot per
    authentication attempt and reports the source as blocked once the window
    holds :data:`AUTH_FAILURE_LIMIT` unresolved attempts.  A blocked request
    is answered with 429 before the token comparison runs.

    :meth:`begin` reads the count and appends the reservation under one lock,
    so a burst of concurrent connections opened while the window is empty
    cannot all pass: at most ``limit`` reservations exist at once.  A failed
    authentication leaves its reservation in place; a successful one calls
    :meth:`release`.

    Memory is bounded.  At most ``max_sources`` sources are tracked: expired
    entries are pruned when a source is accessed, and the least recently used
    source is evicted when a new one would exceed the bound.  Only a bounded
    number of timestamps per source is kept, because older entries can no
    longer affect the decision.

    The limiter is thread-safe.  The admin server runs a synchronous
    before-request hook through ``asyncio.to_thread``, so concurrent
    requests reach these methods from several threads; every read-modify-write
    runs under one lock so no failure is lost and no source is left dangling.

    The key is the resolved client source: the TCP peer address, or the
    rightmost untrusted ``X-Forwarded-For`` hop when the peer is a trusted
    proxy.  Resolution lives in the admin handlers; this class treats the key
    as opaque.

    Args:
        limit: Failures inside *window* that block a source.
        window: Length of the sliding window, in seconds.
        max_sources: Maximum number of sources kept.
        clock: Monotonic clock, injectable for tests.

    Example:
        >>> limiter = AuthFailureLimiter()
        >>> limiter.begin("203.0.113.7") is not None
        True
        >>> for _ in range(AUTH_FAILURE_LIMIT - 1):
        ...     limiter.begin("203.0.113.7")
        >>> limiter.begin("203.0.113.7") is None
        True
        >>> limiter.retry_after("203.0.113.7") is not None
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
        self._lock = threading.Lock()
        self._sequence = 0
        #: ``source -> deque[(sequence, timestamp)]``, oldest first.
        self._failures: collections.OrderedDict[
            str, collections.deque[tuple[int, float]]
        ] = collections.OrderedDict()

    def begin(self, source: str) -> AuthAttempt | None:
        """Reserve one authentication attempt for *source*.

        The count is read and the reservation appended under one lock, so a
        burst of concurrent requests cannot all observe an empty window.
        A failed authentication leaves the reservation in place; a
        successful one must call :meth:`release`.

        Args:
            source: Client source key, normally the resolved client address.

        Returns:
            The reserved attempt, or ``None`` when the source is blocked.
        """
        with self._lock:
            now = self._clock()
            entries = self._failures.get(source)
            if entries is not None:
                self._prune_locked(source, entries)
                entries = self._failures.get(source)
            if entries is not None and len(entries) >= self._limit:
                self._failures.move_to_end(source)
                return None
            if entries is None:
                if len(self._failures) >= self._max_sources:
                    self._evict_locked(now)
                entries = collections.deque()
                self._failures[source] = entries
            else:
                self._failures.move_to_end(source)
            self._sequence += 1
            entries.append((self._sequence, now))
            return AuthAttempt(source, self._sequence)

    def release(self, attempt: AuthAttempt) -> None:
        """Release *attempt* after a successful authentication.

        The attempt and every failure reserved before it leave the window,
        restoring the "a successful login clears the count" behaviour.  A
        failure reserved after this attempt stays, so a success racing with a
        concurrent burst cannot erase it.

        Args:
            attempt: The attempt returned by :meth:`begin`.
        """
        with self._lock:
            entries = self._failures.get(attempt.source)
            if entries is None:
                return
            kept = collections.deque(
                entry for entry in entries if entry[0] > attempt.sequence
            )
            if kept:
                self._failures[attempt.source] = kept
                self._failures.move_to_end(attempt.source)
            else:
                self._failures.pop(attempt.source, None)

    def retry_after(self, source: str) -> float | None:
        """Return the seconds *source* must wait, or ``None`` if it may try.

        Accessing a source prunes its expired failures, so a window that has
        passed always unblocks it.  This is an advisory read for the
        ``Retry-After`` header; admission is decided by :meth:`begin`.

        Args:
            source: Client source key, normally the peer address.

        Returns:
            Seconds until the oldest counted failure leaves the window, or
            ``None`` when the source is not blocked.
        """
        with self._lock:
            entries = self._failures.get(source)
            if entries is None:
                return None
            self._prune_locked(source, entries)
            if not entries:
                return None
            self._failures.move_to_end(source)
            if len(entries) < self._limit:
                return None
            wait = entries[0][1] + self._window - self._clock()
            return wait if wait > 0 else None

    def record_failure(self, source: str) -> None:
        """Record one failed authentication for *source*.

        Kept for callers that record a failure outside the reservation flow.
        The admin handlers use :meth:`begin` instead.

        Args:
            source: Client source key, normally the peer address.
        """
        with self._lock:
            now = self._clock()
            entries = self._failures.get(source)
            if entries is None:
                if len(self._failures) >= self._max_sources:
                    self._evict_locked(now)
                entries = collections.deque()
                self._failures[source] = entries
            else:
                self._failures.move_to_end(source)
            self._sequence += 1
            entries.append((self._sequence, now))
            while len(entries) > self._limit:
                entries.popleft()

    def clear(self, source: str) -> None:
        """Forget the failures recorded for *source*.

        Args:
            source: Client source key, normally the peer address.
        """
        with self._lock:
            self._failures.pop(source, None)

    def _prune_locked(
        self, source: str, entries: collections.deque[tuple[int, float]]
    ) -> None:
        """Drop timestamps that have left the window.  Holds the lock."""
        cutoff = self._clock() - self._window
        while entries and entries[0][1] <= cutoff:
            entries.popleft()
        if not entries:
            self._failures.pop(source, None)

    def _evict_locked(self, now: float) -> None:
        """Make room for one more source, preferring expired entries."""
        for source in list(self._failures):
            self._prune_locked(source, self._failures[source])
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
