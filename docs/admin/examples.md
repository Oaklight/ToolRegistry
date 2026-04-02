# 示例

## 带日志的基本用法

```python
from toolregistry import ToolRegistry

# 创建注册表
registry = ToolRegistry()

# 注册工具
@registry.register
def greet(name: str) -> str:
    """按名称问候某人。"""
    return f"你好，{name}！"

@registry.register
def calculate(a: int, b: int, op: str = "add") -> int:
    """执行计算。"""
    if op == "add":
        return a + b
    elif op == "subtract":
        return a - b
    else:
        raise ValueError(f"未知操作: {op}")

# 启用执行日志
registry.enable_logging(max_entries=1000)

# 启用管理面板
info = registry.enable_admin(port=8081)
print(f"管理面板: {info.url}")

# 保持脚本运行
import time
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    registry.disable_admin()
```

## 远程访问配置

```python
from toolregistry import ToolRegistry
import os

registry = ToolRegistry()

# ... 注册工具 ...

# 从环境获取令牌或生成
token = os.environ.get("ADMIN_TOKEN")

# 启用远程访问
info = registry.enable_admin(
    port=8081,
    remote=True,
    auth_token=token  # None = 自动生成
)

print(f"管理面板: {info.url}")
if info.token:
    print(f"令牌: {info.token}")
```

## 与 FastAPI 集成

```python
from fastapi import FastAPI
from toolregistry import ToolRegistry
from contextlib import asynccontextmanager

registry = ToolRegistry()

# 注册工具
@registry.register
def my_tool(x: int) -> int:
    return x * 2

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时启用管理面板
    info = registry.enable_admin(port=8082)
    print(f"管理面板: {info.url}")
    yield
    # 关闭时禁用
    registry.disable_admin()

app = FastAPI(lifespan=lifespan)

@app.post("/execute")
async def execute_tool(name: str, args: dict):
    tool = registry.get_callable(name)
    if tool:
        return {"result": tool(**args)}
    return {"error": "工具未找到"}
```

## 执行日志分析

```python
from toolregistry import ToolRegistry
from toolregistry.admin import ExecutionStatus

registry = ToolRegistry()
log = registry.enable_logging()

# ... 执行工具 ...

# 分析执行模式
stats = log.get_stats()

print(f"总执行次数: {stats['total_entries']}")
print(f"成功率: {stats['by_status'].get('success', 0) / stats['total_entries'] * 100:.1f}%")
print(f"平均耗时: {stats['avg_duration_ms']:.2f}ms")

# 查找执行最多的工具
by_tool = stats['by_tool']
print("\n按工具统计执行次数:")
for tool_name, count in sorted(by_tool.items(), key=lambda x: -x[1]):
    print(f"  {tool_name}: {count}")

# 获取最近的错误
errors = log.get_entries(status=ExecutionStatus.ERROR, limit=5)
for entry in errors:
    print(f"{entry.tool_name} 中的错误: {entry.error}")
```

## 停止管理面板

```python
# 停止管理面板
registry.disable_admin()

# 检查是否运行中
info = registry.get_admin_info()
if info:
    print(f"仍在运行: {info.url}")
else:
    print("管理面板已停止")
```
