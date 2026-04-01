# Hub 工具使用指南

???+ note "更新日志"
    新增于版本：0.4.2

!!! note "独立包"
    **Hub 工具包更新**：从 0.4.14 版本开始，hub 工具已迁移至独立包 `toolregistry-hub`。您可以通过以下方式安装：

    - `pip install toolregistry-hub`

    这使您可以独立使用 hub 工具，也可以与 ToolRegistry 配合使用。

## 简介

Hub 将常用工具封装为类的方法，包括静态方法和实例方法，作为即用型工具组。这种设计具有以下优势：

1. **组织性**：相关的工具方法被分组在同一个类中，便于管理和维护。
2. **可复用性**：预构建的工具可以直接导入使用，无需重新实现。
3. **一致性**：所有工具遵循相同的接口规范。
4. **可扩展性**：可以轻松添加新的工具类或方法。
5. **安全性和异常处理**：封装的工具提供了更好的安全控制和异常处理能力，优于让模型直接执行命令。

Hub 工具可以使用 `register_from_class` 方法进行注册。详细说明请参阅 [**注册基于类的 Python 工具**](class.md)。

## 使用预定义工具的示例

Hub 还提供了带有即用方法的预定义类。这些工具可以轻松注册和使用，无需额外设置。

```python
from toolregistry import ToolRegistry
from toolregistry.hub import BaseCalculator, Calculator, FileOps

# 创建工具注册表
registry = ToolRegistry()

# 注册 Calculator 工具（带命名空间）
registry.register_from_class(Calculator, with_namespace=True)

# 注册 FileOps 工具（不带命名空间）
registry.register_from_class(FileOps)

# 获取可用工具列表
print(registry.get_available_tools())
# 输出: ['calculator-list_allowed_fns', 'calculator-help', 'calculator-evaluate', 'read_file', 'write_file', ...]
```

在注册时使用 `with_namespace=True` 参数会将类名作为命名空间前缀添加到工具名称中，确保更好的组织性并避免命名冲突。例如：

```python
registry.register_from_class(BaseCalculator, with_namespace=True)
```

这将注册名称为 `base_calculator-add`、`base_calculator-subtract` 等的工具。

使用 `with_namespace` 的优势：

1. 避免不同类中同名方法之间的命名冲突。
2. 更清晰地标识工具来源。
3. 保持命名一致性。