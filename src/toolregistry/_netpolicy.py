"""Outbound address policy shared by every integration.

A URL that comes from a document, an admin request or a configuration file
can name any host, while the process usually runs where the network trusts
its peers.  The policy refuses a host that resolves to anything other than a
globally reachable address, unless the caller opts in.

Known limit: the addresses are resolved here and resolved again when the
connection opens, so a name server that changes its answer in between (DNS
rebinding) defeats the check.  Closing that needs the connection layer to
connect to a pinned address while keeping the original name for ``Host`` and
TLS SNI; track it in #399.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import threading
import time
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlparse

__all__ = [
    "SCHEMES",
    "PrivateAddressError",
    "UnsafeAddressError",
    "clear_address_cache",
    "validate_outbound_url",
    "validate_outbound_url_async",
]

#: Schemes an outbound integration may fetch.
SCHEMES = frozenset({"http", "https"})

#: Seconds a successful check is reused.  A failure is never cached: one DNS
#: hiccup must not lock a host out until the process restarts.  This window
#: is also how long a rebinding answer can go unnoticed (#399).
CACHE_TTL_SECONDS = 60.0

#: Seconds the async resolver waits before failing closed.
RESOLVE_TIMEOUT_SECONDS = 5.0

#: ``(scheme, host, port) -> monotonic expiry`` for successful checks.
_cache: dict[tuple[str, str, int], float] = {}
_cache_lock = threading.Lock()


class UnsafeAddressError(ValueError):
    """A URL names a host the outbound policy refuses to contact."""


class PrivateAddressError(UnsafeAddressError):
    """A host resolves to an address the policy allows only on request.

    The distinction matters to callers that can offer an opt-in: a private
    address has a switch, while a name that does not resolve does not.

    The message does not name the resolved address.  Exception text escapes
    to clients, logs and downstream adapters, and a resolved address is
    internal network topology; callers that need it read :attr:`addresses`.

    Attributes:
        addresses: Every address the resolver returned, in order.
    """

    def __init__(
        self,
        message: str,
        addresses: Sequence[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.addresses: tuple[str, ...] = tuple(addresses or ())


def clear_address_cache() -> None:
    """Forget every cached decision.

    Useful after a network change and in tests; a cached success otherwise
    lives for :data:`CACHE_TTL_SECONDS`.
    """
    with _cache_lock:
        _cache.clear()


def _parse(url: str) -> tuple[str, str, int]:
    """Return ``(scheme, host, port)`` for *url*.

    Args:
        url: The URL to parse.

    Returns:
        The lower-cased scheme, the host with any trailing dot removed, and
        the port, defaulting to the scheme's port.

    Raises:
        UnsafeAddressError: If the URL cannot be parsed, its scheme is not
            HTTP(S), or it names no host.
    """
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:  # malformed IPv6, invalid port, ...
        raise UnsafeAddressError(f"URL is not valid: {exc}") from exc
    if scheme not in SCHEMES:
        raise UnsafeAddressError(
            f"Unsupported URL scheme '{scheme or '(none)'}': "
            "only http and https are allowed"
        )
    if not host:
        raise UnsafeAddressError("URL must include a host")
    # A trailing dot names the same host; drop it so the cache and the
    # resolver see one spelling.
    while host.endswith("."):
        host = host[:-1]
    if not host:
        raise UnsafeAddressError("URL must include a host")
    return scheme, host, port or (443 if scheme == "https" else 80)


def _is_public(address: str) -> bool:
    """Return True when *address* is globally reachable.

    Args:
        address: An IPv4 or IPv6 literal as returned by the resolver.

    Returns:
        True for a globally reachable unicast address.
    """
    ip = ipaddress.ip_address(address)
    if ip.version == 6 and ip.ipv4_mapped is not None:
        # ``::ffff:127.0.0.1`` reaches the same host as ``127.0.0.1``.
        ip = ip.ipv4_mapped
    # ``is_global`` alone is not enough: CPython reports 224.0.0.0/4 as
    # global on 3.10, and an unspecified address is never a target.
    return ip.is_global and not ip.is_multicast and not ip.is_unspecified


def _check(host: str, addresses: list[str]) -> None:
    """Raise unless every resolved *address* is public.

    Args:
        host: The host name that was resolved, for the message.
        addresses: Every address the resolver returned.

    Raises:
        UnsafeAddressError: If the list is empty or any address is not
            globally reachable.
    """
    if not addresses:
        raise UnsafeAddressError(f"Could not resolve '{host}': no address")
    for address in addresses:
        if not _is_public(address):
            raise PrivateAddressError(
                f"Refusing to contact '{host}': the host resolves to a "
                "non-public address. Pass allow_private_hosts=True to allow "
                "loopback, link-local and private hosts.",
                addresses,
            )


def _literal(host: str) -> str | None:
    """Return *host* as an IP literal, or ``None`` when it is a name."""
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None


def _addresses(infos: Any) -> list[str]:
    """Return the address from each ``getaddrinfo`` result."""
    return [str(info[4][0]) for info in infos]


def _resolve(host: str, port: int) -> list[str]:
    """Resolve *host* on the calling thread."""
    return _addresses(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))


async def _resolve_async(
    host: str,
    port: int,
    timeout: float = RESOLVE_TIMEOUT_SECONDS,
) -> list[str]:
    """Resolve *host* through the event loop, bounded by *timeout*."""
    loop = asyncio.get_running_loop()
    infos = await asyncio.wait_for(
        loop.getaddrinfo(host, port, type=socket.SOCK_STREAM),
        timeout=timeout,
    )
    return _addresses(infos)


def _cache_get(scheme: str, host: str, port: int) -> bool:
    key = (scheme, host.lower(), port)
    with _cache_lock:
        expires = _cache.get(key)
    return expires is not None and expires > time.monotonic()


def _cache_put(scheme: str, host: str, port: int) -> None:
    with _cache_lock:
        _cache[(scheme, host.lower(), port)] = time.monotonic() + CACHE_TTL_SECONDS


def validate_outbound_url(url: str, *, allow_private_hosts: bool = False) -> str:
    """Return *url* when its host is public, or raise.

    The host is resolved on the calling thread.  Async callers use
    :func:`validate_outbound_url_async` so the event loop is not blocked.

    Args:
        url: The URL an integration is about to fetch.
        allow_private_hosts: Skip the address check.  Defaults to ``False``.

    Returns:
        *url*, unchanged.

    Raises:
        UnsafeAddressError: If the URL is malformed, its scheme is not
            HTTP(S), its host does not resolve, or (unless
            *allow_private_hosts*) any resolved address is not globally
            reachable.
    """
    scheme, host, port = _parse(url)
    literal = _literal(host)
    if literal is not None:
        if not allow_private_hosts:
            _check(host, [literal])
        return url
    if allow_private_hosts:
        return url
    if _cache_get(scheme, host, port):
        return url
    try:
        addresses = _resolve(host, port)
    except OSError as exc:
        raise UnsafeAddressError(f"Could not resolve '{host}': {exc}") from exc
    _check(host, addresses)
    _cache_put(scheme, host, port)
    return url


async def validate_outbound_url_async(
    url: str,
    *,
    allow_private_hosts: bool = False,
    timeout: float = RESOLVE_TIMEOUT_SECONDS,
) -> str:
    """Async twin of :func:`validate_outbound_url`.

    The resolver runs through the event loop, so a slow name server does not
    block other tasks; *timeout* bounds the wait and fails closed.

    Args:
        url: The URL an integration is about to fetch.
        allow_private_hosts: Skip the address check.  Defaults to ``False``.
        timeout: Seconds to wait for the resolver.

    Returns:
        *url*, unchanged.

    Raises:
        UnsafeAddressError: If the URL is malformed, its scheme is not
            HTTP(S), its host does not resolve, resolution times out, or
            (unless *allow_private_hosts*) any resolved address is not
            globally reachable.
    """
    scheme, host, port = _parse(url)
    literal = _literal(host)
    if literal is not None:
        if not allow_private_hosts:
            _check(host, [literal])
        return url
    if allow_private_hosts:
        return url
    if _cache_get(scheme, host, port):
        return url
    try:
        addresses = await _resolve_async(host, port, timeout)
    except (OSError, asyncio.TimeoutError) as exc:
        raise UnsafeAddressError(f"Could not resolve '{host}': {exc}") from exc
    _check(host, addresses)
    _cache_put(scheme, host, port)
    return url
