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
