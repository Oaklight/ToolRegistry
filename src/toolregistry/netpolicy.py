"""Public entry point for the outbound address policy.

:func:`validate_outbound_url` (and its async twin) answer one question: may
this URL be dialed?  The host is resolved, and every answer must be a
globally routable unicast address.  Loopback, link-local, private, multicast,
reserved and the special-purpose transition ranges are refused unless the
caller passes ``allow_private_hosts=True``.  A NAT64 or IPv4-mapped address is
judged by the IPv4 address it embeds: the well-known prefix
``64:ff9b::/96`` is unwrapped and re-checked, while the local-use prefix
``64:ff9b:1::/48`` is refused as a whole because its embedding layout differs
and cannot be read from the low 32 bits.

The policy ends at the dial.  It does not follow redirects, it does not pin
the resolved address to the connection (a second resolution at connect time
can return a different answer, #399), and it does not strip credentials from
a cross-origin redirect.  A caller that fetches a URL someone else supplied
owns those decisions.

``toolregistry._netpolicy`` remains importable and resolves to the same
objects; new code should import from this module.
"""

from __future__ import annotations

from ._netpolicy import (
    SCHEMES,
    PrivateAddressError,
    UnsafeAddressError,
    clear_address_cache,
    validate_outbound_url,
    validate_outbound_url_async,
)

__all__ = [
    "SCHEMES",
    "PrivateAddressError",
    "UnsafeAddressError",
    "clear_address_cache",
    "validate_outbound_url",
    "validate_outbound_url_async",
]
