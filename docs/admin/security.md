# Security Considerations

## Local vs Remote Access

| Mode | Binding | Authentication | Use Case |
|------|---------|----------------|----------|
| Local (default) | `127.0.0.1` | Optional | Development, testing |
| Remote | `0.0.0.0` | Required | Production, multi-user |

## Token Authentication

When `remote=True` or `auth_token` is provided:

- All API requests require the `Authorization: Bearer <token>` header
- Tokens are compared using constant-time comparison to prevent timing attacks
- Auto-generated tokens are 32-character hex strings (128 bits of entropy)

The web UI shell (`GET /`) is the one exception: a browser cannot attach an
`Authorization` header to a top-level navigation, so the static document is
served without a token. It contains no registry data. On the first API call
the page prompts for the token, stores it in `localStorage`, and retries; the
successful request issues an `HttpOnly` session cookie so the prompt appears
once per browser session. Concurrent API calls share a single prompt, and a
rejected token is retried only once, so a typo cannot loop the dialog.

### Authentication Throttling

Failed authentication is throttled per client source. Five failed attempts
from one source inside 60 seconds get `429 Too Many Requests` with a
`Retry-After` header (whole seconds, at least 1). Each attempt reserves a slot
under one lock **before** the token comparison, so a burst of connections
opened while the window is empty cannot all pass and guess in parallel, and
one comparison's worth of work is all a blocked source gets.

- A malformed `Authorization` header and a wrong token each leave their
  reservation in place and count as one failure.
- A successful request — a valid Bearer token or a valid session cookie —
  releases its reservation together with the failures recorded before it; a
  failure reserved after it, by a request still in flight, stays.
- A request with no credentials releases its reservation, because a browser
  that has not logged in yet is not guessing.
- The table holds at most 1024 sources. Expired entries are pruned when a
  source is accessed, and the least recently used source is evicted when a new
  one would exceed the bound, so varying the source address cannot grow memory
  without limit.

The key is the TCP peer address by default. Behind a reverse proxy every
client shares the proxy's address and is throttled together, so list the
proxies whose forwarding header may be believed:

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
registry.enable_admin(trusted_proxies=["127.0.0.1", "10.0.0.0/8"])
```

Entries are addresses or CIDR ranges and are validated at construction
(`AdminServer(..., trusted_proxies=...)` takes the same argument). When the
peer is trusted, `X-Forwarded-For` is walked right to left, trusted hops are
skipped, and the first untrusted address becomes the key. Prepended entries
cannot steer that choice, because the trusted proxy appends the hop it
actually saw. A peer that is not in the list ignores the header entirely, and
an empty or malformed chain falls back to the peer address.

The proxy must *replace* an inbound `X-Forwarded-For` with the address it saw,
not append to it. The panel never resolves the address, so run the proxy on
the same host or trust only addresses that clients cannot reach directly.

## Cross-Origin Access

The panel only answers `Access-Control-Allow-Origin` for same-origin requests
(`Origin` matching the `Host` header). A page on another origin cannot read
API responses or drive state-changing endpoints through the user's browser,
which matters because the default local panel runs without authentication.
Non-browser clients are unaffected: CORS is a browser enforcement mechanism.
To embed the panel in another origin, serve both through one origin with a
reverse proxy rather than loosening the panel's CORS policy.

State-changing requests are refused in middleware, not merely hidden by the
response header: every `/api/` `POST`, `PUT`, `PATCH` and `DELETE` whose
`Origin` is not this server, or whose `Sec-Fetch-Site` is `cross-site`, gets
403 before routing. These methods must also send
`Content-Type: application/json`; any other media type gets 415. This closes
the form-submission path, which a page can use with `text/plain` and no
preflight.

## Local Commands

An MCP source can be a stdio command, a script path, or any transport that is
not an `http(s)://` URL. Preview and registration execute such a transport, so
`POST /api/sources/preview` and `POST /api/sources/register` answer 403 while
the panel has no authentication token. Configure `auth_token=...`, or run with
`remote=True` (which generates one), before using a local command source. HTTP
MCP sources, OpenAPI sources and Python modules are not affected by this
guard.

## Outbound Addresses

An MCP source that names an `http(s)://` or `ws(s)://` URL is resolved and
checked before its transport opens. Loopback, link-local, private, multicast
and reserved addresses are refused by default. Pass `allow_private_hosts=True`
to `register(..., source="mcp")`, `register_mcp_tools*()` or the admin register
payload to reach a server on the same host or a private network; a local panel
should enable a token before granting that opt-in. The refusal names the switch
and does not echo the resolved address.

A redirect cannot reach a host the check never saw: mcp v1 HTTP clients are
created with redirects disabled, and mcp v2 follows only same-origin redirects.

## Frame Protection

Every admin response carries `X-Frame-Options: DENY` and
`Content-Security-Policy: frame-ancestors 'none'`. The shell loads without a
token so it can prompt for one, and an embedded copy would inherit the
origin's `localStorage` token; refusing frames keeps another page from
clickjacking the panel's enable/disable, import and rename controls.

## Best Practices

!!! warning "Production Deployment"
    For production deployments, always:

    1. Use `remote=True` with a strong custom token
    2. Deploy behind a reverse proxy (nginx, Caddy) with HTTPS
    3. Restrict access using firewall rules
    4. Consider disabling the web UI (`serve_ui=False`) if not needed

!!! tip "Token Management"
    - Store tokens securely (environment variables, secrets manager)
    - Rotate tokens periodically
    - Use different tokens for different environments

## Reverse Proxy Sub-path Deployment

The admin panel can be served behind a reverse proxy at a sub-path (e.g. `/admin/openapi/`). The UI automatically resolves its API base URL from the current page URL, so API calls are correctly routed through the proxy prefix.

When deploying behind a reverse proxy, the proxy must strip the sub-path prefix before forwarding to the admin panel. For example, with Caddy:

```
handle /admin/openapi* {
    basic_auth {
        admin $2a$14$...  # bcrypt hash
    }
    uri strip_prefix /admin/openapi
    reverse_proxy admin-backend:8001
}
```

The same-origin check compares the `Origin` netloc with the `Host` header, so
the proxy must forward the client's `Host` unchanged (nginx:
`proxy_set_header Host $host;`). A proxy that rewrites `Host` to an internal
address makes every state-changing request look cross-origin, and it is
refused with 403.

The admin panel itself does not enforce authentication when `remote=False` — use the reverse proxy's auth mechanism (e.g. `basic_auth` in Caddy) to protect access.
