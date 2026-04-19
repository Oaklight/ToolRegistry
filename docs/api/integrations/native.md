# 原生集成

本节介绍 ToolRegistry 库的原生 Python 类集成功能。

## 架构概览

原生集成支持将 Python 类方法直接注册为 ToolRegistry 框架中的工具。该集成提供了一种将现有 Python 类转换为可调用工具的无缝方式：

### 核心组件

1. **ClassToolIntegration**：主集成类，处理类方法注册

   - 自动检测静态方法与实例方法
   - 在需要时处理类实例化
   - 管理命名空间分配，实现有组织的工具层次结构

2. **方法注册逻辑**：智能注册，适应不同的类模式
   - 静态方法直接从类注册
   - 实例方法触发自动类实例化
   - 混合方法类型会生成适当的错误信息

### 设计理念

- **零配置**：注册 Python 类所需的设置最少
- **智能检测**：自动检测方法类型和实例化需求
- **命名空间管理**：基于类名自动生成命名空间
- **错误透明性**：针对常见集成问题提供清晰的错误信息

### 主要特性

- **自动方法发现**：扫描类中的公共可调用方法
- **智能实例化**：处理静态方法和实例方法的注册
- **命名空间支持**：从类名自动生成命名空间
- **MRO 遍历**：`traverse_mro` 参数控制是否通过方法解析顺序遍历包含从父类继承的方法。当为 `True`（默认值）时，从所有父类（不包括 `object`）继承的方法也会被包含，子类方法具有优先权。当为 `False` 时，只注册直接定义在该类上的方法。
- **错误处理**：针对有问题的类结构提供清晰的错误信息
- **异步支持**：完全兼容 async/await 模式
- **基于反射**：使用 Python 的内省能力进行方法发现

### 注册模式

#### 静态方法类

```python
class Calculator:
    @staticmethod
    def add(a: int, b: int) -> int:
        return a + b
```

方法无需实例化即可直接注册。

#### 实例方法类

```python
class FileManager:
    def __init__(self, base_path: str):
        self.base_path = base_path

    def read_file(self, filename: str) -> str:
        # Implementation
```

类会自动实例化，实例方法被注册。

#### 混合方法类

```python
class MixedClass:
    @staticmethod
    def static_method():
        pass

    def instance_method(self):
        pass
```

自动检测并适当处理。

#### 继承方法注册

默认情况下（`traverse_mro=True`），从父类继承的方法也会被注册：

```python
class BaseTools:
    @staticmethod
    def base_method(x: int) -> int:
        return x * 2

class DerivedTools(BaseTools):
    @staticmethod
    def derived_method(x: int) -> int:
        return x * 3

# Default behavior (traverse_mro=True): both base_method and derived_method are registered
# With traverse_mro=False: only derived_method is registered
```

## API 参考

### ClassToolIntegration

处理与 Python 类集成以进行方法注册的类。

::: toolregistry.integrations.native.integration.ClassToolIntegration
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

## 模块概览

### 原生模块

原生集成主模块。

::: toolregistry.integrations.native
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

### 原生工具函数

用于原生集成的实用函数。

::: toolregistry.integrations.native.utils
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true
