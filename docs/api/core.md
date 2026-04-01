# Core Classes

!!! warning "本页尚未翻译"
    本页内容尚未翻译为中文。以下为英文原文，中文翻译将在后续版本中提供。

The core classes provide the fundamental abstractions for tool management, execution, and integration within the ToolRegistry ecosystem.

## Components

| Class | Description | Reference |
|-------|-------------|-----------|
| [ToolRegistry](core/toolregistry.md) | Central orchestrator for tool registration, execution, and schema generation | Primary entry point |
| [Tool](core/tool.md) | Represents an individual tool with metadata, parameters, and execution logic | Tool abstraction |
| [Executor](core/executor.md) | Pluggable execution backends (thread/process) with cancellation and timeout | Execution engine |
| [Events](events.md) | Change event types and callback mechanism for registry state changes | Event infrastructure |
| [Permissions](permissions.md) | Rule-based authorization framework for controlling tool execution | Permission system |

## Architecture

```
ToolRegistry (Orchestrator)
    ├── Tool (Abstraction)
    │   ├── ToolMetadata (Behavioral metadata)
    │   └── ToolTag (Classification tags)
    ├── Executor (Execution Engine)
    │   ├── ThreadBackend
    │   └── ProcessPoolBackend
    ├── Permission System
    │   ├── PermissionPolicy (Rule engine)
    │   ├── PermissionRule (Match + result)
    │   └── PermissionHandler (ASK protocol)
    └── Integration Modules
        ├── MCP Integration
        ├── OpenAPI Integration
        ├── LangChain Integration
        └── Native Integration
```

## See Also

- [Helper Classes](helpers.md) — Parameter validation and utility functions
- [Integration Modules](integrations.md) — Framework-specific integration classes
- [Tool Wrappers](wrappers.md) — Adapter classes for external tool formats
