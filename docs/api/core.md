# 核心类

核心类提供了 ToolRegistry 生态系统中工具管理、执行和集成的基础抽象。

## 组件

| 类 | 描述 | 参考 |
|-------|-------------|-----------|
| [ToolRegistry](core/toolregistry.md) | 工具注册、执行和 Schema 生成的中央编排器 | 主入口 |
| [Tool](core/tool.md) | 表示一个具有元数据、参数和执行逻辑的独立工具 | 工具抽象 |
| [Executor](core/executor.md) | 可插拔的执行后端（线程/进程），支持取消和超时 | 执行引擎 |
| [Events](events.md) | 变更事件类型和注册表状态变化的回调机制 | 事件基础设施 |
| [Permissions](permissions.md) | 基于规则的授权框架，用于控制工具执行 | 权限系统 |

## 架构

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

## 参见

- [辅助类](helpers.md) — 参数验证和实用函数
- [集成模块](integrations.md) — 框架特定的集成类
- [工具包装器](wrappers.md) — 外部工具格式的适配器类
