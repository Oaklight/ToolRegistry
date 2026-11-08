# Source persistence hook

The admin panel can preview and register a source, but it does not own a
configuration file: registration is process-local. A downstream server that
does own one installs a **source persistence hook**. The panel then hands every
source change to it, reports the persistence outcome, and exposes the hook's
per-source status.

Without a hook, nothing changes: registration and `GET /api/sources` keep
their existing response shapes.

## The hook

A hook is any object with three methods. `source_hook` accepts it on
`AdminServer` or `enable_admin`:

```python
from toolregistry import AdminServer, ToolRegistry


class ConfigHook:
    def __init__(self, manager):
        self.manager = manager

    def persist(self, change):
        # Store the change, then return the source's status record.
        return self.manager.apply(change).to_dict()

    def writable(self):
        return self.manager.config_path is not None

    def statuses(self):
        return self.manager.to_dicts()


server = AdminServer(
    ToolRegistry(),
    port=8081,
    source_hook=ConfigHook(manager),
)
```

| Method | Contract |
|--------|----------|
| `persist(change)` | Store the change and return its status record. Raise `SourcePersistenceError` when it cannot be stored; the message is shown to the operator. |
| `writable()` | Whether the backing configuration can be written. |
| `statuses()` | Every source's status record, including failed and excluded sources with no tools. |

The record returned by `persist` and each record from `statuses` must carry at
least `id`, `kind`, `detail`, `namespace`, `status` and `last_error`, plus
`names`. `status` is one of `applied`, `excluded` or `failed`. `detail` and
`last_error` must be redacted: the panel shows them to the operator.

## The change

`persist` receives a `SourceChange`:

| Field | Meaning |
|-------|---------|
| `action` | `add`, `remove` or `replace`. The admin panel emits `add`; remove and replace come from downstream callers that already own the source diff. |
| `kind` | `openapi`, `mcp` or `python`. |
| `payload` | The declaration as submitted to the panel. It may contain credentials. |
| `namespace` | The requested namespace, or `None`. |
| `selected` | The tool names the operator kept, or `None` for all of them. |
| `source_id` | Existing source id for remove and replace; `None` for add. |

`payload` can carry an auth token, request headers, `env` values or command
arguments. A hook must neither log nor echo it, and it must redact whatever it
stores for display. The panel never logs `payload` itself.

## Registration response

With a hook, a successful registration adds two fields:

```json
{
  "kind": "python",
  "registered": ["isleap"],
  "count": 1,
  "persisted": true,
  "source": {"id": "src_0123456789abcdef", "status": "applied", "...": "..."}
}
```

`source` is the record returned by `persist`, which is how a client learns the
id of the source it just registered.

When `persist` fails, the registration still succeeded — the tools are live —
so the response stays `200` and reports the failure instead of claiming the
registration failed:

```json
{
  "kind": "python",
  "registered": ["isleap"],
  "count": 1,
  "persisted": false,
  "persist_error": "configuration is read-only"
}
```

A `5xx` is reserved for the case where nothing was applied.

## The sources listing

With a hook, `GET /api/sources` keeps its `sources` array exactly as before
and adds two siblings:

```json
{
  "sources": [{"type": "python", "detail": "calendar", "...": "..."}],
  "source_status": [
    {"id": "src_0123456789abcdef", "kind": "python", "status": "applied", "...": "..."},
    {"id": "src_fedcba9876543210", "kind": "mcp", "status": "failed", "last_error": "...", "...": "..."}
  ],
  "config_writable": true
}
```

`source_status` is passed through verbatim, so a failed or excluded source
with no registered tools is still visible. Join it to `sources` on the record
`id`, or on `kind`/`detail`/`namespace` when no id is at hand. The built-in
Sources tab reads only `sources`, so an installed hook does not change it.

A hook that raises from `statuses()` or `writable()` does not break the
listing: the failure is logged, `source_status` is empty and
`config_writable` is `false`.

## Failure behaviour

- **A persist failure keeps the tools registered.** The registry mutation has
  already happened; the response reports `persisted: false` and the names that
  landed, so a client can retry the write without re-registering.
- **A status failure degrades the listing, not the panel.** The tool-derived
  `sources` array is still served.
- **The hook is trusted code.** It runs in the panel process and sees the full
  declaration, credentials included. Install only hooks you trust.
