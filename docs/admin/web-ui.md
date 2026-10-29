# Web UI Guide

The built-in web UI provides a visual interface for managing your ToolRegistry.

## Interface Overview

The web UI is organized into several sections:

1. **Tools Panel**: Lists all registered tools with enable/disable toggles
2. **Namespaces Panel**: Shows namespaces with bulk enable/disable controls
3. **Logs Panel**: Displays execution history with filtering options
4. **State Panel**: Provides export/import functionality

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
