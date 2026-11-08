# 配置

`enable_admin()` 方法接受以下参数：

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `host` | `str` | `"127.0.0.1"` | 绑定的主机地址 |
| `port` | `int` | `8081` | 监听的端口号 |
| `serve_ui` | `bool` | `True` | 是否在根路径提供 Web UI |
| `remote` | `bool` | `False` | 是否允许远程连接 |
| `auth_token` | `str \| None` | `None` | API 访问的认证令牌 |
| `allow_private_hosts` | `bool` | `False` | 允许面板从回环、链路本地或私有地址拉取 OpenAPI 规范并注册其工具 |

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

=== "本地 API 源"

    ```python
    # 面板默认拒绝回环、链路本地与私有地址（#370）。
    # 需要从本机 API 注册工具时显式开启：
    info = registry.enable_admin(allow_private_hosts=True)
    ```

## OpenAPI 规范检查

预览（`POST /api/sources/preview`）与注册（`POST /api/sources/register`）在列出
或注册工具之前，会编译文档中的每一个 schema 正则。

- 集成会转成工具的操作（`get`、`post`、`put`、`delete`）中的 `pattern` 关键字和
  每个 `patternProperties` 键都会被编译。只检查 `parameters[].schema` 与
  `application/json` 请求体——也就是会变成已发布工具参数的部分。
- 无法编译的正则会被拒绝，返回 `400 Bad Request`。消息会指出工具名与 schema
  路径（例如 `tool 'api_get_item' parameters['id'].schema.pattern: ...`），并且
  注册表保持不变。
- 安装了可选的 `regex` 包时使用它（请求时校验用的同一引擎），否则使用标准库
  `re`。回退更严格：只有 `regex` 才接受的正则（如变长后行断言或 `\p{...}`）会在
  注册时被拒绝，而不是之后被静默忽略。
- 名称恰好是数据关键字（`default`、`enum`、`example` 等）的属性仍会作为 schema
  遍历，因此其下的错误正则仍会被发现。schema 对象上的数据值不是正则，不会被
  编译。

需要这项检查，是因为失败过去出现得更晚：安装 `regex` 时每次调用都会返回 500，
未安装时约束则被静默丢弃。

## AdminInfo 对象

`enable_admin()` 方法返回一个 `AdminInfo` 对象，包含以下属性：

| 属性 | 类型 | 描述 |
|------|------|------|
| `host` | `str` | 服务器绑定的主机地址 |
| `port` | `int` | 服务器监听的端口号 |
| `url` | `str` | 访问管理面板的完整 URL |
| `token` | `str \| None` | 认证令牌（如果启用了认证） |
