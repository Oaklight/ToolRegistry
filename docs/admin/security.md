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

管理面板在 `remote=False` 时不强制认证——请使用反向代理的认证机制（如 Caddy 的 `basic_auth`）来保护访问。
