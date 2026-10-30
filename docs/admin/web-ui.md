# Web UI Guide

The built-in web UI provides a visual interface for managing your ToolRegistry.

## Interface Overview

The panel is a console: a fixed header, a section rail down the left edge, and
the selected section's content on the right.

- **Tools**: lists registered tools with enable/disable toggles
- **Namespaces**: namespaces with bulk enable/disable controls
- **Sources**: where each tool came from
- **Register**: connect a new OpenAPI, MCP or Python source and pick the tools to keep
- **Logs**: execution history with filtering options
- **Permissions**: the evaluated policy result per tool
- **Schema**: the schemas published to models, plus the discover index
- **State**: export/import and registry-wide settings

The rail collapses to icons with the toggle at its foot (the choice is
remembered), and below 900px it becomes a drawer opened by the header's menu
button. The header stays pinned to the top and shares the rail's surface, so
the two read as one frame around the content.

The overview cards at the top of the Tools section are links: the total opens
the unfiltered list, enabled and disabled open it filtered to that status, and
the namespace count opens the Namespaces panel.

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

### Registering tools

The Register section connects to a source and lists what it offers **before
anything is registered**:

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
- **Override**: edit the tool's description, `ToolTag`s and custom tags

An override installs an edited copy of the registered tool and keeps the
displaced definition, so **Restore original** puts the source's own definition
back. The registry keeps the same key and the same callable, which means calls,
logs and permissions behave exactly as before; only the advertised metadata
changes. Overridden tools are marked in the modal, and
`GET /api/overrides` lists every override with its current and original
definition.

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

- Export current disabled state as JSON
- Import previously exported state
- Invalid files are rejected before the confirmation dialog, and a malformed
  request returns `400` without changing the current disabled set
- Names must resolve to a registered tool or namespace; unknown names return
  `400` rather than silently clearing the disabled set
- Useful for backup/restore scenarios

## Registry Settings

The State panel also controls the namespace separator (`-` or `.`). Applying a
change **renames every namespaced tool immediately** — for example
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
