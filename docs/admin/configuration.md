# Configuration

The `enable_admin()` method accepts the following parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"127.0.0.1"` | The host address to bind to |
| `port` | `int` | `8081` | The port number to listen on |
| `serve_ui` | `bool` | `True` | Whether to serve the web UI at root path |
| `remote` | `bool` | `False` | Whether to allow remote connections |
| `auth_token` | `str \| None` | `None` | Authentication token for API access |

## Configuration Examples

=== "Local Development"

    ```python
    # Default: local access only, no authentication
    info = registry.enable_admin()
    print(f"Admin panel: {info.url}")
    ```

=== "Remote Access"

    ```python
    # Remote access with auto-generated token
    info = registry.enable_admin(remote=True)
    print(f"Admin panel: {info.url}")
    print(f"Token: {info.token}")  # Auto-generated secure token
    ```

=== "Custom Token"

    ```python
    # Remote access with custom token
    info = registry.enable_admin(
        remote=True,
        auth_token="my-secure-token-123"
    )
    ```

=== "API Only"

    ```python
    # Disable web UI, serve API only
    info = registry.enable_admin(serve_ui=False)
    ```

## AdminInfo Object

The `enable_admin()` method returns an `AdminInfo` object with the following attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `host` | `str` | The host address the server is bound to |
| `port` | `int` | The port number the server is listening on |
| `url` | `str` | The full URL to access the admin panel |
| `token` | `str \| None` | The authentication token (if auth is enabled) |
