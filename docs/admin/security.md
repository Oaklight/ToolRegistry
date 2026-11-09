# 安全考虑

## 本地访问 vs 远程访问

| 模式 | 绑定地址 | 认证 | 使用场景 |
|------|----------|------|----------|
| 本地（默认） | `127.0.0.1` | 可选 | 开发、测试 |
| 远程 | `0.0.0.0` | 必需 | 生产、多用户 |

## 令牌认证

当 `remote=True` 或提供了 `auth_token` 时：

- 所有 API 请求都需要 `Authorization: Bearer <token>` 头
- 令牌使用常量时间比较，防止时序攻击
- 自动生成的令牌是 32 字符的十六进制字符串（128 位熵）

Web UI 外壳（`GET /`）是唯一的例外：浏览器无法在顶层导航中附加
`Authorization` 头，因此这个静态文档不需要令牌即可加载，其中也不包含任何
注册表数据。页面首次调用 API 时会提示输入令牌，将其存入 `localStorage` 后
重试；成功请求会下发 `HttpOnly` 会话 Cookie，因此每个浏览器会话只需输入一次。
并发的 401 共享同一个提示框，被拒绝的令牌只重试一次，输入错误不会无限弹窗。

### 认证限流

认证失败按客户端来源限流。同一来源在 60 秒内失败五次后，会得到
`429 Too Many Requests`，并带有 `Retry-After` 头（整数秒，至少为 1）。每次尝试
都会在令牌比较**之前**在同一把锁内预留一个名额，因此窗口为空时并发打开的一批
连接无法全部通过并并行猜测；对被封禁的来源，最多只付出一次比较的代价。

- `Authorization` 头格式错误和令牌错误都会保留各自的名额，各计一次失败。
- 成功的请求——有效的 Bearer 令牌或有效的会话 Cookie——会释放自己的名额，连同
  在此之前的失败记录一并清除；在它之后由仍在处理中的请求预留的失败则保留。
- 没有携带凭据的请求会释放名额，因为尚未登录的浏览器并不是在猜测。
- 表最多保留 1024 个来源。访问某个来源时会清理过期条目；新来源会超出上限时，
  淘汰最久未使用的来源，因此变换来源地址无法让内存无限增长。

默认限流键是 TCP 对端地址。反向代理之后，所有客户端共享代理地址、被一起限流；
此时可列出允许信任其转发头的代理：

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
registry.enable_admin(trusted_proxies=["127.0.0.1", "10.0.0.0/8"])
```

条目为地址或 CIDR 网段，在构造时校验（`AdminServer(..., trusted_proxies=...)`
接受同样的参数）。当对端受信时，`X-Forwarded-For` 从右往左遍历，跳过受信的跳，
第一个非受信地址成为限流键。客户端自行前置的条目无法左右该选择，因为受信代理
追加的是它实际看到的跳。不在列表中的对端会完全忽略该头；空头或畸形链回退到
对端地址。

代理必须用自己看到的地址**覆盖**传入的 `X-Forwarded-For`，而不是追加。面板不会
解析该地址，因此请把代理跑在同一主机上，或只信任客户端无法直接访问的地址。

## 跨源访问

面板只对同源请求返回 `Access-Control-Allow-Origin`（`Origin` 与 `Host` 头一致）。
其他来源的页面无法通过用户浏览器读取 API 响应或触发会改变状态的接口——这很
重要，因为默认的本地面板没有鉴权。非浏览器客户端不受影响：CORS 是浏览器侧的
限制机制。若要把面板嵌入其他来源，应通过反向代理让两者处于同一来源，而不是
放宽面板的 CORS 策略。

状态改变请求会在中间件中被拒绝，而不只是被响应头挡住：所有 `/api/` 下的
`POST`、`PUT`、`PATCH` 与 `DELETE`，只要 `Origin` 不是本服务器，或
`Sec-Fetch-Site` 为 `cross-site`，都会在路由前返回 403。这些方法还必须发送
`Content-Type: application/json`，其他媒体类型返回 415。这堵住了表单提交路径：
页面可以用 `text/plain` 发送请求而无需预检。

## 本地命令

MCP 来源可以是 stdio 命令、脚本路径，或任何不是 `http(s)://` 的传输。预览与注册
会执行这类传输，因此当面板没有认证令牌时，`POST /api/sources/preview` 与
`POST /api/sources/register` 返回 403。在使用本地命令来源前，请配置
`auth_token=...`，或以 `remote=True` 启动（该模式会自动生成令牌）。HTTP MCP
来源、OpenAPI 来源与 Python 模块不受此限制。

## 出站地址

MCP 来源的 `http(s)://` 或 `ws(s)://` 地址会在建立传输前解析并校验。回环、
链路本地、私有、组播与保留地址默认被拒绝。通过
`register(..., source="mcp")`、`register_mcp_tools*()` 或管理面板注册请求传入
`allow_private_hosts=True`，才能访问本机或内网服务器；本地面板在授予该开关前
应先启用令牌。拒绝信息会点名该开关，且不回显解析到的地址。

重定向无法到达未经校验的主机：mcp v1 的 HTTP 客户端禁用重定向，mcp v2 只跟随
同源重定向。

## 框架保护

所有管理响应都带有 `X-Frame-Options: DENY` 与
`Content-Security-Policy: frame-ancestors 'none'`。外壳无需令牌即可加载以便
提示输入令牌，而被嵌入的副本会继承该来源的 `localStorage` 令牌；拒绝框架可
防止其他页面通过点击劫持操作面板的启用/禁用、导入与重命名控件。

## 最佳实践

!!! warning "生产部署"
    对于生产部署，请始终：

    1. 使用 `remote=True` 并设置强自定义令牌
    2. 部署在反向代理（nginx、Caddy）后面，启用 HTTPS
    3. 使用防火墙规则限制访问
    4. 如果不需要，考虑禁用 Web UI（`serve_ui=False`）

!!! tip "令牌管理"
    - 安全存储令牌（环境变量、密钥管理器）
    - 定期轮换令牌
    - 不同环境使用不同令牌

## 反向代理子路径部署

管理面板可以在反向代理的子路径（如 `/admin/openapi/`）下提供服务。UI 会自动根据当前页面 URL 计算 API 基础地址，确保 API 请求通过代理前缀正确路由。

部署在反向代理后面时，代理必须在转发前剥离子路径前缀。以 Caddy 为例：

```
handle /admin/openapi* {
    basic_auth {
        admin $2a$14$...  # bcrypt 哈希值
    }
    uri strip_prefix /admin/openapi
    reverse_proxy admin-backend:8001
}
```

同源判断会比较 `Origin` 的 netloc 与 `Host` 头，因此代理必须原样转发
客户端的 `Host`（nginx：`proxy_set_header Host $host;`）。若代理把 `Host`
改写成内部地址，所有状态改变请求都会被视为跨源并返回 403。

管理面板在 `remote=False` 时不强制认证——请使用反向代理的认证机制（如 Caddy 的 `basic_auth`）来保护访问。
