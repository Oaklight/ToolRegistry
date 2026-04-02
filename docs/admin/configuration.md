# 配置

`enable_admin()` 方法接受以下参数：

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `host` | `str` | `"127.0.0.1"` | 绑定的主机地址 |
| `port` | `int` | `8081` | 监听的端口号 |
| `serve_ui` | `bool` | `True` | 是否在根路径提供 Web UI |
| `remote` | `bool` | `False` | 是否允许远程连接 |
| `auth_token` | `str \| None` | `None` | API 访问的认证令牌 |

## 配置示例

=== "本地开发"

    ```python
    # 默认：仅本地访问，无需认证
    info = registry.enable_admin()
    print(f"管理面板: {info.url}")
    ```

=== "远程访问"

    ```python
    # 远程访问，自动生成令牌
    info = registry.enable_admin(remote=True)
    print(f"管理面板: {info.url}")
    print(f"令牌: {info.token}")  # 自动生成的安全令牌
    ```

=== "自定义令牌"

    ```python
    # 远程访问，使用自定义令牌
    info = registry.enable_admin(
        remote=True,
        auth_token="my-secure-token-123"
    )
    ```

=== "仅 API"

    ```python
    # 禁用 Web UI，仅提供 API
    info = registry.enable_admin(serve_ui=False)
    ```

## AdminInfo 对象

`enable_admin()` 方法返回一个 `AdminInfo` 对象，包含以下属性：

| 属性 | 类型 | 描述 |
|------|------|------|
| `host` | `str` | 服务器绑定的主机地址 |
| `port` | `int` | 服务器监听的端口号 |
| `url` | `str` | 访问管理面板的完整 URL |
| `token` | `str \| None` | 认证令牌（如果启用了认证） |
