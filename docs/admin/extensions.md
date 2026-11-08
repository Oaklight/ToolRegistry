# Admin Panel Extensions

An extension adds a section to the admin panel. It contributes a navigation
item, a panel, one asset directory, and optionally HTTP routes under
`/ext/<name>`. The panel keeps ownership of authentication, the shell, and the
asset path; an extension does not touch them.

The contract is versioned. Version 1 is the only version this release
provides.

## Declaring an extension

An extension is an object with the attributes below and a `register` method.

| Attribute | Required | Meaning |
|-----------|----------|---------|
| `name` | yes | Lower-case identifier matching `^[a-z][a-z0-9_-]*$`. It becomes the URL segment `/ext/<name>` and the asset directory key. |
| `title` | yes | Locale map for the navigation label, for example `{"en": "Clock", "zh": "时钟"}`. |
| `assets` | with a tab | Directory on disk that `entry` and `styles` are read from. Required when the extension declares `nav` or any asset. |
| `entry` | with a tab | Browser module path under `assets/ext/<name>/`, ending in `.js`. Required when `nav` is present. |
| `requires_api` | yes | Contract version the extension targets. Must equal `ADMIN_EXTENSION_API` (`1`). |
| `styles` | no | Sequence of `.css` paths under `assets/ext/<name>/`. |
| `icon` | no | SVG markup for the navigation item. The default is a grid glyph. |
| `nav` | no | Mapping with an optional `group` translation key and an integer `order` (default `100`). |
| `register` | yes | Called once with an `AdminContext`. |

`name`, `title`, `requires_api` and `register` are validated before the
listener starts. A violation raises `AdminExtensionError` naming the
extension, and `AdminServer.start()` fails; the panel never serves a
half-mounted extension.

An extension that only contributes HTTP routes omits `nav`, `assets`, `entry`
and `styles`. Its routes are mounted and `GET /api/extensions` reports
`"nav": null` and `"entry": null`; the panel shows no tab for it.

Paths that do not start with `assets/ext/<name>/`, contain dot segments, or
use a suffix outside `.css` / `.js` are refused.

## Registering routes

`register` receives an `AdminContext`. Its methods register handlers relative
to `/ext/<name>`:

```python
from pathlib import Path

from toolregistry import ADMIN_EXTENSION_API, AdminServer, ToolRegistry


class ClockExtension:
    name = "clock"
    title = {"en": "Clock", "zh": "时钟"}
    entry = "assets/ext/clock/main.js"
    styles = ("assets/ext/clock/style.css",)
    requires_api = ADMIN_EXTENSION_API
    assets = Path("/srv/toolregistry/extensions/clock/static")
    nav = {"group": "utilities", "order": 20}

    def register(self, ctx):
        ctx.get("/now", self.now)
        ctx.get("/zones/<path:zone>", self.zone)

    def now(self, request):
        return {"now": "tick"}

    def zone(self, request, zone):
        return {"zone": zone}


registry = ToolRegistry()
server = AdminServer(registry, port=8081, extensions=[ClockExtension()])
info = server.start()
```

The helpers are `ctx.get`, `ctx.post`, `ctx.put`, `ctx.patch` and `ctx.delete`.
Each takes a path and a handler; the decorator form is also accepted:

```python
@ctx.get("/status")
def status(request):
    return {"ok": True}
```

Handlers follow the panel's handler convention: they receive the request first
and then any path parameters, and they return a JSON-serialisable value.
Synchronous handlers run in a worker thread. The context also exposes
`registry`, `api_prefix`, `api_url(path)` and `asset_url(path)`.

Registering the same method and path twice raises `AdminExtensionError`.

## The manifest

`GET /api/extensions` returns every mounted extension in declaration order:

```json
{
  "api_version": 1,
  "extensions": [
    {
      "name": "clock",
      "title": {"en": "Clock", "zh": "时钟"},
      "icon": null,
      "nav": {"group": "utilities", "order": 20},
      "entry": "assets/ext/clock/main.js",
      "styles": ["assets/ext/clock/style.css"],
      "api_prefix": "/ext/clock",
      "requires_api": 1
    }
  ]
}
```

The endpoint requires the same authentication as the rest of the panel. An
API-only extension appears with `"nav": null` and `"entry": null`.

`nav.group` is a translation key, not a display label: the shell renders
`group.<key>` when a dictionary defines it, and otherwise shows the key
itself. Group keys use the same lower-case charset as `name`.

## The browser module

The shell fetches the manifest, adds a navigation item and a panel, then
imports `entry` as an ES module. The module exports `register` and may export
`unmount`:

```javascript
// assets/ext/clock/main.js
export async function register({ container, api, i18n, manifest }) {
    const heading = document.createElement('h2');
    heading.textContent = manifest.title[i18n.lang] || manifest.title.en;
    container.appendChild(heading);

    const value = document.createElement('p');
    container.appendChild(value);

    const tick = async () => {
        const data = await api.get('/now');
        value.textContent = data.now;
    };
    await tick();
}

export function unmount() {
    // Release timers, sockets or listeners registered by register().
}
```

`register` receives:

- `container`: the panel's content element. It is empty and belongs to the
  extension.
- `api`: a client for the extension's routes. `api.get(path)`,
  `api.post(path, body)`, `api.put`, `api.patch`, `api.delete` and
  `api.request(path, options)` all prepend the extension prefix and use the
  panel's authentication. `api.url(path)` returns the URL without sending a
  request.
- `i18n`: `{lang, t(key, params)}`. `t` reads the panel's shared translation
  map; extension-specific strings can be selected from `lang` directly.
- `manifest`: the entry from `GET /api/extensions`.

`unmount` is optional. It is called if the loader removes the extension, and
should release anything `register` started.

A language switch relabels the navigation item from `title`, but the panel
does not re-render the extension's content. An extension that translates its
own text should read `i18n.lang` when it renders and refresh itself when the
language changes.

A module that throws while loading or registering does not break the panel:
the failure is logged to the console and that extension's navigation item,
panel and stylesheets are removed.

## Assets

Files under the declared `assets` directory are served at
`/assets/ext/<name>/...`. Only `.css` and `.js` are served, the request path
is checked for dot segments, and the resolved file must stay inside the
directory, so a symlink cannot escape it.

When the UI is served, extension assets share the shell's authentication
exemption: the browser must load the panel's scripts before it can present a
token prompt. The handler serves only declared files with the whitelisted
content types. Extension assets are therefore public to anyone who can reach
the panel port, even on a token-protected panel. Do not put secrets in them.

## Security and versioning

- **One authentication level.** Extension routes inherit the panel's policy.
  There is no per-extension token or role.
- **Cross-site protection applies.** State-changing requests to `/ext/...`
  are subject to the same origin, `Sec-Fetch-Site` and JSON content-type rules
  as `/api/...`.
- **Version handshake.** `requires_api` is checked on the server at startup
  and again in the browser against `api_version`. A mismatch refuses the
  extension with its name in the message; it is never mounted silently.
- **Trust.** An extension is operator-installed code. Its browser module runs
  with the panel's privileges, and its `icon` string is inserted as SVG
  markup. There is no sandbox, so the panel's XSS boundary is only as strong
  as the extension's own correctness. Install only extensions you trust.
