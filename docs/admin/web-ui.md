# Web UI Guide

The built-in web UI provides a visual interface for managing your ToolRegistry.

## Interface Overview

The panel is a console: a fixed header, a section rail down the left edge, and
the selected section's content on the right.

- **Tools**: every registered tool, grouped by namespace, with the overview
  strip, the filters and the per-tool and per-namespace controls
- **Sources**: where the tools came from, plus **Add source** — the form that
  connects an OpenAPI, MCP or Python source and picks the tools to keep
- **Logs**: execution history with filtering options
- **Permissions**: the evaluated policy result per tool
- **Schema**: the schemas published to models, plus the discover index
- **Settings**: registry-wide settings, state export/import, and an **About**
  card with the package versions and links to the repository, PyPI and the docs

There is no separate Namespaces page: a namespace is a grouping of tools, so it
lives in the Tools list. Each group header carries the bulk controls (enable or
disable everything under it, THINK and DEFER for all its tools), clicking the
name collapses or expands the group, and the overview's namespace count
collapses every group so the list reads as a namespace summary.

The rail collapses to icons with the toggle at its foot (the choice is
remembered), and below 900px it becomes a drawer opened by the header's menu
button. The header stays pinned to the top and shares the rail's surface, so
the two read as one frame around the content. It carries only the colour
scheme, the light/dark toggle, the language switcher and a connection dot:
versions and package links live in Settings, and each section refreshes itself
(the connection dot polls on its own).

The overview cards at the top of the Tools section are links: the total opens
the unfiltered list, enabled and disabled open it filtered to that status, and
the namespace count opens the Namespaces panel.

## Tool discovery and deferred tools

`discover_tools` and `call_deferred` are not built in by default: they are
registered by `registry.enable_tool_discovery()` (the hub server enables
discovery for its MCP endpoint, a plain `ToolRegistry` does not). Until that
runs they do not exist, so they never appear in the Tools list.

That matters because `defer` and discovery are one mechanism, not two. A tool
marked deferred is left out of the schema the model sees, and only
`discover_tools` can bring it back. With discovery off, deferring a tool
therefore makes it *unreachable* rather than deferred. The Tools section says
so: when any tool is deferred and discovery is off, a notice above the table
states how many and why, and the Schema section's **Discover Tools** sub-tab
stays visible with the same explanation instead of disappearing.

Discovery can be turned on and off from the panel:

- the notice above the table, and the **Discover Tools** sub-tab while it is
  off, carry an **Enable tool discovery** button;
- once enabled, the sub-tab shows the `discover_tools` description and a
  **Disable tool discovery** control, which asks for confirmation because every
  deferred tool becomes unreachable again;
- the **Settings** section states the effective state, how many deferred tools
  a switch would restore, and the mode: **Auto** follows the deferred set,
  while **On** and **Off** are explicit choices that the notice's buttons also
  set. A registry in **Auto** turns discovery on exactly while a tool is
  deferred, so the notice only appears after an explicit **Off**.

This is a registry change, not a configuration edit: it takes effect
immediately and is not written to the config file, so a restart returns to
whatever the process configured. The same three operations are available as
`GET /api/discovery`, `POST /api/discovery/enable` and
`POST /api/discovery/disable`.

## Schema

The Schema section renders the schemas published to models. The format picker
offers llm-rosetta's canonical, vendor-neutral names — `chat_completions`,
`open_responses`, `messages`, `google_generate`, `google_interactions` and
`rosetta_ir` — and `GET /api/schema?format=…` accepts them as well as the older
spellings (`openai-chat`, `anthropic`, …), which remain valid.

## Moving between sections

The four sections that describe where tools come from are connected, so a
number is always a way into the list that explains it:

| From | Click | Lands in |
|---|---|---|
| Overview | total / enabled / disabled | Tools, filtered by status |
| Overview | namespaces | Tools with every group collapsed — the namespace summary |
| Overview | a namespace count, in a group | the group collapses or expands |
| Tools | a source badge | Sources, filtered by that source type |
| Sources | namespace name | Tools, filtered by namespace |
| Sources | "Show N tools" | Tools, filtered by source and namespace |
| Sources | "Register from this source" | Add source, pre-filled with the kind, detail and namespace |
| Add source | a previewed tool name | that tool's detail modal |
| Add source | "View registered tools" (after registering) | Tools, filtered by the namespace just used |

## Themes

Two colour schemes ship with the panel — **Paper** (warm neutrals, brass
accent) and **Slate** (cool neutrals, blue accent) — each in a light and a dark
mode. Choose a scheme in the header and toggle the mode next to it; both are
stored in `localStorage` and applied before the first paint, so a reload does
not flash the default.

The look is split in two, and the split is enforced by tests rather than left
to review. A **scheme** declares values only: `css/base.css` holds one block per
scheme and mode, and a block may contain nothing but custom properties. A
**component** — `css/components.css` and the markup — decides where those
values land: box model, layout, pointer behaviour. A scheme selector that names
anything but the scheme and the mode (for example
`[data-scheme="slate"] .card`) is rejected by `tests/test_admin_theme.py`, and
so is a token one scheme declares but another omits.

Adding a scheme means one structural block, one block per mode, a name in
`SCHEMES` in `js/core/theme.js`, the option in the header select, and a label in
both dictionaries. The contract test then covers it.

### Adding a source

**Add source** in the Sources section connects to a source and lists what it
offers **before anything is registered**:

1. Pick the kind — **OpenAPI** (spec URL or path), **MCP** (server URL, or a
   stdio command) or **Python** (a module, optionally narrowed to a class or
   function).
2. Optionally set a namespace; preview names include it, so what you tick is
   exactly what gets registered.
3. For OpenAPI and MCP sources, set **Authentication** — a bearer token, basic
   credentials, or extra headers written one per line as `Name: value`. An
   `Authorization` header typed here wins over the fields above, so a scheme
   the panel does not model can still be sent. Credentials are used for the
   preview and for registration, and are never written to the registry.
4. **Preview tools** lists every tool the source advertises, with the ones
   already registered marked. **Select all**, **Select none**, **Invert** and
   **Refresh** work on the list.
5. Tick the tools to keep and press **Register selected**. Only the ticked
   names are sent, so a source can never add a tool nobody asked for.

Errors — an unreachable server, an unimportable module, a spec without
`servers[]` — are reported in the panel instead of being registered silently.
A server that requires a token reports an empty error; the panel says so and
points at the Authentication fields.

Names that a model API would reject are flagged before registration. OpenAI and
Anthropic accept `[A-Za-z0-9_-]` up to 64 characters, and Gemini additionally
allows dots, so a name such as `fs/file_search_glob` — which an MCP server may
advertise — is stored faithfully by the registry but makes a provider schema
invalid. The preview lists the offending names, and a tool whose registered
name is outside the strict set carries a `!` badge in the Tools table.

## Tool Management

- Click the toggle switch next to a tool to enable/disable it
- Disabled tools show the reason (if provided)
- Click on a tool name to view its full schema, metadata, and permissions in a detail modal
- Search tools by name using the search bar
- Filter tools by `ToolTag` badges (e.g., READ_ONLY, DESTRUCTIVE, NETWORK)

### Metadata Badges

Each tool row displays metadata badges for quick identification:

- **ToolTag badges** (color-coded): READ_ONLY, DESTRUCTIVE, NETWORK, FILE_SYSTEM, SLOW, PRIVILEGED
- **Locality badge**: `local` or `remote` (shown when not `any`)
- **`async`**: Indicates the tool is asynchronous

### Runtime Metadata Control

The `think_augment` and `defer` properties can be toggled at runtime directly from the UI:

- **Per-tool checkboxes**: Each tool row has dedicated Think and Defer columns with checkboxes
- **Per-namespace checkboxes**: Namespace header rows include checkboxes that apply to all tools within the namespace
- The Think checkbox controls whether the generated schema exposes the reserved `toolcall_reason` rationale field
- Changes take effect immediately without restarting the service
- Only `think_augment` and `defer` are modifiable at runtime (other metadata fields are read-only for safety)

### Tool Detail Modal

Clicking a tool name opens a detail modal with three sections:

- **Schema**: Full JSON schema of the tool's parameters
- **Metadata**: All `ToolMetadata` fields with interactive toggles for `think_augment` and `defer`
- **Permissions**: Permission evaluation result showing applicable rules and decisions
- **Override**: the action sits in the modal header next to the tool name; it edits
  the tool's description, title, `ToolTag`s, custom tags
  and the four execution hints (`read_only_hint`, `destructive_hint`,
  `idempotent_hint`, `open_world_hint`)

An override installs an edited copy of the registered tool and keeps the
displaced definition, so **Restore original** puts the source's own definition
back. The registry keeps the same key and the same callable, which means calls,
logs and permissions behave exactly as before; only the advertised metadata
changes. Overridden tools are marked in the modal, and
`GET /api/overrides` lists every override with its current and original
definition.

Execution hints are tri-state. **Default (derived)** leaves the field unset,
so the registry derives it from tags when it builds a schema. **Yes** and
**No** pin the value and stop the derivation. `GET /api/tools/{name}`
returns the raw tri-state fields next to the resolved `execution_hints`,
so a form can show "unset" separately from an explicit value.

## Namespace Management

- Enable/disable all tools in a namespace with a single click
- Toggle `think_augment` and `defer` for all tools in a namespace
- View tool counts per namespace
- See enabled/disabled breakdown

## Execution Log Viewer

- Filter logs by tool name or status (success, error, timeout, rejected)
- Press Enter in the tool filter or click Apply to run the query
- Expand an entry to see its arguments, result, warnings, and — for failures —
  the exception type and a collapsible traceback
- Filters survive the panel's Refresh and enable/disable actions (a full page reload resets them)
- Clear logs when needed (a confirmation is required)
- View aggregate statistics, including timeouts

## State Import/Export

State export and import live in the **Settings** section alongside the registry
settings and the About card.

- Export current disabled state as JSON
- Import previously exported state
- Invalid files are rejected before the confirmation dialog, and a malformed
  request returns `400` without changing the current disabled set
- Names must resolve to a registered tool or namespace; unknown names return
  `400` rather than silently clearing the disabled set
- Useful for backup/restore scenarios

## Registry Settings

The Settings section also controls the namespace separator. Only the hyphen is
offered: it is the one separator every model API accepts, while OpenAI and
Anthropic reject dots in tool names. A registry already configured with `.`
keeps that value listed, marked as the current one, so it can be moved to `-`.
Applying a change **renames every namespaced tool immediately** — for example
`math_utils-square` becomes `math_utils.square`. Calls that still use the old
names pass no longer resolve, and existing log entries keep the old names. The
UI asks for confirmation before applying the change and refreshes every tab
afterwards.

## Language Switching (i18n)

The Web UI supports English and Chinese. A language switcher dropdown is located in the top-right corner of the header.

- Select **EN** for English or **中文** for Chinese
- The preference is persisted in `localStorage` and restored on next visit
- All UI elements update immediately — tabs, table headers, buttons, filters, toast messages, modal dialogs, and empty states
- Dynamic content (tool lists, log entries, statistics) is re-rendered in the selected language when switching
