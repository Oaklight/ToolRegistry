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
- **`think`**: Indicates think-augmented function calling is enabled
- **`defer`**: Indicates the tool is deferred (excluded from initial prompt)
- **`async`**: Indicates the tool is asynchronous

### Runtime Metadata Control

The `think_augment` and `defer` properties can be toggled at runtime directly from the UI:

- **Per-tool toggles**: Each tool row has small indigo toggle switches for `think` and `defer`
- **Per-namespace toggles**: Namespace header rows include toggles that apply to all tools within the namespace
- Changes take effect immediately without restarting the service
- Only `think_augment` and `defer` are modifiable at runtime (other metadata fields are read-only for safety)

### Tool Detail Modal

Clicking a tool name opens a detail modal with three tabs:

- **Schema**: Full JSON schema of the tool's parameters
- **Metadata**: All `ToolMetadata` fields with interactive toggles for `think_augment` and `defer`
- **Permissions**: Permission evaluation result showing applicable rules and decisions

## Namespace Management

- Enable/disable all tools in a namespace with a single click
- Toggle `think_augment` and `defer` for all tools in a namespace
- View tool counts per namespace
- See enabled/disabled breakdown

## Execution Log Viewer

- Filter logs by tool name or status
- View execution details including arguments and results
- Clear logs when needed
- View aggregate statistics

## State Import/Export

- Export current disabled state as JSON
- Import previously exported state
- Useful for backup/restore scenarios

## Language Switching (i18n)

The Web UI supports English and Chinese. A language switcher dropdown is located in the top-right corner of the header.

- Select **EN** for English or **中文** for Chinese
- The preference is persisted in `localStorage` and restored on next visit
- All UI elements update immediately — tabs, table headers, buttons, filters, toast messages, modal dialogs, and empty states
- Dynamic content (tool lists, log entries, statistics) is re-rendered in the selected language when switching
