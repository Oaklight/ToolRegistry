# Outbound Address Policy

`toolregistry.netpolicy` answers one question before a connection is opened:
**may this URL be dialed?** A URL that comes from a document, an admin request
or a configuration file can name any host, while the process usually runs on a
network that trusts its peers. The policy resolves the host and refuses every
answer that is not a globally reachable unicast address.

```python
from toolregistry.netpolicy import UnsafeAddressError, validate_outbound_url

validate_outbound_url("https://api.example.com/openapi.json")  # ok
validate_outbound_url("http://127.0.0.1:8000/spec.json")       # PrivateAddressError
```

## API

| Object | Purpose |
|--------|---------|
| `validate_outbound_url(url, *, allow_private_hosts=False)` | Resolve `url`'s host and return `url` unchanged, or raise |
| `validate_outbound_url_async(url, *, allow_private_hosts=False, timeout=5.0)` | Same check, resolved through the event loop |
| `resolve_outbound_url(url, *, allow_private_hosts=False)` | Same check, and return `(url, addresses)` with the addresses it judged |
| `resolve_outbound_url_async(url, *, allow_private_hosts=False, timeout=5.0)` | Async twin of the above |
| `SCHEMES` | `frozenset({"http", "https", "ws", "wss"})` |
| `UnsafeAddressError` | Base class, a `ValueError` |
| `PrivateAddressError` | Subclass, raised when the host resolves to a non-public address |
| `clear_address_cache()` | Forget every cached decision |

### `validate_outbound_url`

```python
def validate_outbound_url(url: str, *, allow_private_hosts: bool = False) -> str: ...
```

The synchronous form resolves on the calling thread. Async callers use
`validate_outbound_url_async` so the event loop is not blocked; both forms
share one cache.

### `resolve_outbound_url`

```python
def resolve_outbound_url(url: str, *, allow_private_hosts: bool = False) -> tuple[str, tuple[str, ...]]: ...
```

The policy is identical to `validate_outbound_url`; the result also carries
the addresses that were judged, in resolver order. A transport that can pin
the connect address — `httpclient`'s `resolve_to`, for example — takes them
instead of resolving the name again. That second resolution is the DNS
rebinding window between the check and the dial.

```python
from toolregistry.netpolicy import resolve_outbound_url

url, addresses = resolve_outbound_url("https://api.example.com/spec.json")
# Pass `addresses` to a transport that accepts a pinned connect address.
```

An IP-literal host returns its literal as the only address. A cache hit
returns the addresses the cached check approved, not a fresh resolver answer,
so a rebinding inside the cache window cannot redirect a pinned connection.
An empty resolver answer is refused like any other failed lookup.

One difference from the validate pair: with `allow_private_hosts=True` the
resolve pair still resolves, because the caller needs the addresses, while
`validate_outbound_url` returns without a DNS lookup. An unchecked lookup is
never cached, so it cannot satisfy a later validating call.

### Errors

`PrivateAddressError` carries `addresses`, the full resolver answer in order.
The message does not name the resolved address: exception text escapes to
clients, logs and downstream adapters, and a resolved address is internal
network topology. Callers that need the address read the attribute.

The two classes are separate because the remedies differ. A private address
has a switch (`allow_private_hosts=True`); a name that does not resolve, a
malformed URL or an unsupported scheme does not.

```python
from toolregistry.netpolicy import PrivateAddressError

try:
    validate_outbound_url("http://localhost:11434")
except PrivateAddressError as exc:
    print(exc.addresses)  # ('127.0.0.1',)
```

## What is refused

| Category | Examples |
|----------|----------|
| Unsupported scheme | `file:`, `ftp:`, a missing scheme |
| Missing or unparsable host | `http://`, malformed IPv6 literal, invalid port |
| Names that do not resolve | NXDOMAIN, resolver failure, timeout |
| Loopback, link-local, unspecified, multicast, reserved | `127.0.0.1`, `::1`, `169.254.1.1`, `fe80::1`, `0.0.0.0`, `224.0.0.1` |
| Private ranges | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7` |
| Special-purpose transition ranges | `::/96`, `2001::/32` (Teredo), `2002::/16` (6to4), `64:ff9b:1::/48` |
| Other special-purpose blocks | `192.0.0.0/24`, `192.88.99.0/24`, `198.18.0.0/15`, `240.0.0.0/4`, `100::/64`, `2001:2::/48`, `2001:10::/28`, `2001:20::/28`, `2001:db8::/32`, `3fff::/20`, `5f00::/16` |

`ipaddress.is_global` is the allowlist, but the IANA special-purpose table
behind it changes between interpreter releases. The ranges above are also
refused explicitly, so a later table change cannot silently open one of them.

Every address the resolver returns must be public. One private answer among
public ones is enough to refuse the URL.

### NAT64 and IPv4-mapped addresses

An IPv4-mapped address (`::ffff:a.b.c.d`) and the NAT64 well-known prefix
(`64:ff9b::/96`) reach the IPv4 host in their low 32 bits, but `is_global`
judges the IPv6 prefix. Without special handling, `64:ff9b::7f00:1` would
look public while reaching `127.0.0.1`. The policy unwraps both and re-checks
the embedded IPv4 address.

The NAT64 local-use prefix (`64:ff9b:1::/48`) is refused as a whole. RFC 8215
places the IPv4 address at a deployment-specific position, so no fixed bit
range can be trusted: `64:ff9b:1::808:808` has `8.8.8.8` in its low 32 bits
but its embedded target is `0.0.0.0`.

## Caching

A successful check is cached for 60 seconds (`CACHE_TTL_SECONDS`) under
`(scheme, host, port)`. A failure is never cached: one DNS hiccup must not
lock a host out until the process restarts. Call `clear_address_cache()` after
a network change, or in tests.

The cache window is also how long a changing DNS answer can go unnoticed —
see the contract below.

## Resolution timeout

`validate_outbound_url_async` bounds the resolver with `timeout` (default 5.0
seconds, `RESOLVE_TIMEOUT_SECONDS`) and fails closed with
`UnsafeAddressError`. The synchronous form has no timeout of its own; the
platform resolver decides.

## Where the policy applies

Core applies the check at every point that opens a connection from a URL the
caller did not necessarily choose:

- `validate_spec_url()` and `validate_spec_url_async()`,
  `load_openapi_spec()`, `load_openapi_spec_async()`,
  `extract_base_url_from_specs()`
- `HttpClientConfig` and both base-URL clients
- `OpenAPISource`
- `MCPClient`, `register_mcp_tools*()`, `register(..., source="mcp")`,
  `MCPSource`
- `registry.enable_admin()`

Each entry point takes `allow_private_hosts=True` to reach a local or internal
API. The admin panel exposes its own switch through
`registry.enable_admin(allow_private_hosts=True)`; `GET /api/info` reports the
value, and the OpenAPI form shows a hint when the server refuses private
addresses.

## What the policy does not do

The policy ends at the dial. It does not:

- **Follow redirects.** A 3xx to an unvalidated address is refused on the spec
  load path; opt in with `follow_redirects=True` when the target is trusted.
  Redirect revalidation on the tool-call path is tracked in #399.
- **Pin the resolved address to the connection.** The address is resolved
  again when the connection opens, so a name server that changes its answer
  in between (DNS rebinding) defeats the check. Closing that needs the
  connection layer to connect to a pinned address while keeping the original
  name for `Host` and TLS SNI.
- **Strip credentials from a cross-origin redirect.**

A caller that fetches a URL someone else supplied owns those decisions.

## Compatibility

`toolregistry._netpolicy` remains importable and resolves to the same objects.
New code should import from `toolregistry.netpolicy`.

## See also

- [Migrating to 0.20](../../guides/migrating-to-0.20.md) — the opt-ins that
  restore the old behaviour
- [Admin Panel: Security](../../admin/security.md) — the admin panel's own
  switch and throttling
