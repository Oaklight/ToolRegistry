"""Outbound address policy shared by every integration.

A URL that comes from a document, an admin request or a configuration file
can name any host, while the process usually runs where the network trusts
its peers.  The policy refuses a host that resolves to anything other than a
globally reachable address, unless the caller opts in.

This module is the implementation; ``toolregistry.netpolicy`` is the public
entry point and re-exports the same objects.

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

#: Schemes an outbound integration may open a connection to.  ``ws`` and
#: ``wss`` are the WebSocket twins of ``http`` and ``https``: same host, same
#: default port, so one policy covers both transports.
SCHEMES = frozenset({"http", "https", "ws", "wss"})

#: Port used when the URL names none.
_DEFAULT_PORTS = {"http": 80, "https": 443, "ws": 80, "wss": 443}

#: Seconds a successful check is reused.  A failure is never cached: one DNS
#: hiccup must not lock a host out until the process restarts.  This window
#: is also how long a rebinding answer can go unnoticed (#399).
CACHE_TTL_SECONDS = 60.0

#: Seconds the async resolver waits before failing closed.
RESOLVE_TIMEOUT_SECONDS = 5.0

#: ``(scheme, host, port) -> monotonic expiry`` for successful checks.
_cache: dict[tuple[str, str, int], float] = {}
_cache_lock = threading.Lock()

#: IPv4 and IPv6 ranges that ``is_global`` alone cannot be trusted to refuse.
#:
#: ``is_global`` is the allowlist, but the IANA special-purpose table behind it
#: changes between interpreter releases, so a range's verdict is not stable
#: across the versions this project supports.  Measured with the interpreters
#: available locally (3.10, 3.11, 3.14); CI runs the policy tests on its
#: 3.10-3.13 matrix, but those tests assert the policy's answer, not the
#: ``is_global`` value itself.
#:
#: * ``::/96`` (IPv4-compatible), ``192.88.99.0/24`` (6to4 relay anycast),
#:   ``64:ff9b::/96`` (NAT64), ``2001:20::/28`` (ORCHIDv2) and ``5f00::/16``
#:   (SRv6 SIDs) report ``is_global=True`` on every version measured - those
#:   are live bypasses.
#: * The remaining ranges already report ``False``, but they are pinned here
#:   so a later CPython table change (the 3.13 release added several
#:   special-purpose blocks) cannot silently open them again.
#:
#: NAT64 is handled separately: the well-known prefix is public by design, so
#: its embedded IPv4 address decides; the local-use prefix has a
#: deployment-specific layout, so no fixed bit position can be trusted and the
#: prefix is refused instead.
_SPECIAL_PURPOSE_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        # IPv4
        "192.0.0.0/24",  # IETF protocol assignments; a mixed block, refused
        #                  as a unit (192.0.0.9/32 is global anycast).
        "192.88.99.0/24",  # 6to4 relay anycast (deprecated); is_global=True.
        "198.18.0.0/15",  # benchmarking; is_global=False today.
        "240.0.0.0/4",  # reserved, includes 255.255.255.255.
        # IPv6
        "::/96",  # IPv4-compatible (deprecated); ::7f00:1 reaches 127.0.0.1.
        "100::/64",  # discard-only; is_global=False today.
        "2001::/32",  # Teredo; embeds an IPv4 address.
        "2001:2::/48",  # benchmarking; is_global=False today.
        "2001:10::/28",  # ORCHID; is_global=False today.
        "2001:20::/28",  # ORCHIDv2; is_global=True.
        "2001:db8::/32",  # documentation; is_global=False today.
        "2002::/16",  # 6to4; embeds an IPv4 address.
        "3fff::/20",  # documentation; is_global=False today.
        "5f00::/16",  # SRv6 SIDs; is_global=True.
        # NAT64 local-use prefix (RFC 8215): refused as a whole.  Its IPv4
        # embedding position depends on the deployment, so no fixed bit range
        # can be trusted - 64:ff9b:1::808:808 has 8.8.8.8 in the low 32 bits
        # while its embedded target is 0.0.0.0.
        "64:ff9b:1::/48",
    )
)

#: The NAT64 well-known prefix (RFC 6052).  Its IPv6 form is reported as
#: public, so the IPv4 address in the low 32 bits decides whether the target
#: is allowed.  The local-use prefix is handled by refusing it as a whole
#: (see :data:`_SPECIAL_PURPOSE_NETWORKS`): its IPv4 embedding position is
#: deployment-dependent, so no fixed bit range can be trusted.
_NAT64_WELL_KNOWN = ipaddress.ip_network("64:ff9b::/96")


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
        UnsafeAddressError: If the URL cannot be parsed, its scheme is not in
            :data:`SCHEMES`, or it names no host.
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
            "only http, https, ws and wss are allowed"
        )
    if not host:
        raise UnsafeAddressError("URL must include a host")
    # A trailing dot names the same host; drop it so the cache and the
    # resolver see one spelling.
    while host.endswith("."):
        host = host[:-1]
    if not host:
        raise UnsafeAddressError("URL must include a host")
    return scheme, host, port or _DEFAULT_PORTS[scheme]


def _embedded_ipv4(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Address | None:
    """Return the IPv4 address *ip* encodes, when it encodes one.

    An IPv4-mapped address (``::ffff:a.b.c.d``) and the NAT64 well-known
    prefix (``64:ff9b::/96``) reach the IPv4 host whose address occupies the
    low 32 bits.  ``is_global`` judges the IPv6 prefix instead: it reports
    ``64:ff9b::/96`` as public, which makes ``64:ff9b::7f00:1`` look like a
    public target although it reaches 127.0.0.1.

    The NAT64 local-use prefix (``64:ff9b:1::/48``) is not unwrapped here:
    RFC 8215 places the IPv4 address elsewhere, so this function would read
    the wrong bits.  That prefix is refused as a whole instead.

    Args:
        ip: A parsed IPv4 or IPv6 address.

    Returns:
        The embedded IPv4 address, or ``None`` when *ip* is not a mapped or
        well-known NAT64 address.
    """
    if not isinstance(ip, ipaddress.IPv6Address):
        return None
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in _NAT64_WELL_KNOWN:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def _is_public(address: str) -> bool:
    """Return True when *address* may be dialed.

    ``is_global`` is the allowlist, followed by explicit refusals for
    addresses it cannot be trusted to classify: multicast, unspecified,
    link-local, loopback and reserved, and the version-dependent
    special-purpose ranges in :data:`_SPECIAL_PURPOSE_NETWORKS`.  An
    IPv4-mapped or NAT64 address is judged by the IPv4 address it embeds.

    Args:
        address: An IPv4 or IPv6 literal as returned by the resolver.

    Returns:
        True for a globally reachable unicast address.
    """
    ip = ipaddress.ip_address(address)
    embedded = _embedded_ipv4(ip)
    if embedded is not None:
        ip = embedded
    if (
        ip.is_multicast
        or ip.is_unspecified
        or ip.is_link_local
        or ip.is_loopback
        or ip.is_reserved
    ):
        return False
    if not ip.is_global:
        return False
    return not any(
        ip in network
        for network in _SPECIAL_PURPOSE_NETWORKS
        if network.version == ip.version
    )


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
        UnsafeAddressError: If the URL is malformed, its scheme is not in
            :data:`SCHEMES`, its host does not resolve, or (unless
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
        UnsafeAddressError: If the URL is malformed, its scheme is not in
            :data:`SCHEMES`, its host does not resolve, resolution times
            out, or (unless *allow_private_hosts*) any resolved address is
            not globally reachable.
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
