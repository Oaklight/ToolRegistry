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

## Cross-Origin Access

The panel only answers `Access-Control-Allow-Origin` for same-origin requests
(`Origin` matching the `Host` header). A page on another origin cannot read
API responses or drive state-changing endpoints through the user's browser,
which matters because the default local panel runs without authentication.
Non-browser clients are unaffected: CORS is a browser enforcement mechanism.
To embed the panel in another origin, serve both through one origin with a
reverse proxy rather than loosening the panel's CORS policy.

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

The admin panel itself does not enforce authentication when `remote=False` — use the reverse proxy's auth mechanism (e.g. `basic_auth` in Caddy) to protect access.
