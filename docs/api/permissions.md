# Permissions

The permissions module provides the authorization framework for controlling tool execution in ToolRegistry. It implements a rule-based policy engine with handler protocols for interactive authorization.

## Overview

The module consists of four main components:

- **PermissionResult** -- Three-state enum (`ALLOW`, `DENY`, `ASK`)
- **PermissionRule** -- Match predicate paired with a result
- **PermissionPolicy** -- Ordered rule collection with first-match-wins evaluation
- **PermissionHandler / AsyncPermissionHandler** -- Protocols for resolving `ASK` results

For usage guide and examples, see [Permission System](../usage/permissions.md).

## Types

::: toolregistry.permissions.types
    options:
        show_source: true
        show_root_heading: true

## Handler Protocols

::: toolregistry.permissions.handler
    options:
        show_source: true
        show_root_heading: true

## Policy and Rules

::: toolregistry.permissions.policy
    options:
        show_source: true
        show_root_heading: true

## Built-in Rules

::: toolregistry.permissions.builtin_rules
    options:
        show_source: true
        show_root_heading: true
        show_root_toc_entry: true
