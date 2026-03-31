# 权限

权限模块为 ToolRegistry 中的工具执行控制提供授权框架。它实现了基于规则的策略引擎和用于交互式授权的处理器协议。

## 概述

该模块由四个主要组件组成：

- **PermissionResult** -- 三态枚举（`ALLOW`、`DENY`、`ASK`）
- **PermissionRule** -- 匹配谓词与结果的配对
- **PermissionPolicy** -- 有序规则集合，采用首次匹配生效的评估方式
- **PermissionHandler / AsyncPermissionHandler** -- 用于解析 `ASK` 结果的协议

使用指南和示例请参阅[权限系统](../usage/permissions.md)。

## 类型

::: toolregistry.permissions.types
    options:
        show_source: true
        show_root_heading: true

## 处理器协议

::: toolregistry.permissions.handler
    options:
        show_source: true
        show_root_heading: true

## 策略和规则

::: toolregistry.permissions.policy
    options:
        show_source: true
        show_root_heading: true

## 内置规则

::: toolregistry.permissions.builtin_rules
    options:
        show_source: true
        show_root_heading: true
        show_root_toc_entry: true
