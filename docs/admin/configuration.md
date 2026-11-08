# Configuration

The `enable_admin()` method accepts the following parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"127.0.0.1"` | The host address to bind to |
| `port` | `int` | `8081` | The port number to listen on |
| `serve_ui` | `bool` | `True` | Whether to serve the web UI at root path |
| `remote` | `bool` | `False` | Whether to allow remote connections |
| `auth_token` | `str \| None` | `None` | Authentication token for API access |
| `allow_private_hosts` | `bool` | `False` | Allow the panel to fetch an OpenAPI spec from, and register tools on, a loopback, link-local or private address |

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

=== "Local API Sources"

    ```python
    # The panel refuses loopback, link-local and private addresses by default
    # (#370).  Opt in to register tools from an API on this machine:
    info = registry.enable_admin(allow_private_hosts=True)
    ```

## OpenAPI Spec Checks

Preview (`POST /api/sources/preview`) and registration
(`POST /api/sources/register`) compile every schema pattern in the document
before listing or registering a tool.

- A `pattern` keyword and every `patternProperties` key in an operation the
  integration turns into a tool (`get`, `post`, `put`, `delete`) are compiled.
  Only `parameters[].schema` and the `application/json` request body are
  inspected — the parts that become published tool parameters.
- A pattern that does not compile is refused with `400 Bad Request`. The
  message names the tool and the schema path (for example
  `tool 'api_get_item' parameters['id'].schema.pattern: ...`), and the
  registry is left untouched.
- The engine is `regex` when that optional package is installed — the same
  engine request-time validation uses — and the standard library `re`
  otherwise. The fallback is stricter: a pattern that only `regex` accepts,
  such as a variable-length lookbehind or `\p{...}`, is rejected at
  registration instead of being silently ignored later.
- Property names that happen to be data keywords (`default`, `enum`,
  `example`, ...) are walked as schemas, so a bad pattern under them is still
  caught. Data values on a schema object are not patterns and are not
  compiled.

This check exists because the failure used to arrive later: with `regex`
installed every call to the tool failed with a 500, and without it the
constraint was silently dropped.

## AdminInfo Object

The `enable_admin()` method returns an `AdminInfo` object with the following attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `host` | `str` | The host address the server is bound to |
| `port` | `int` | The port number the server is listening on |
| `url` | `str` | The full URL to access the admin panel |
| `token` | `str \| None` | The authentication token (if auth is enabled) |
