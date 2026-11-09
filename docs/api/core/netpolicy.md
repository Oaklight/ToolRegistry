# 出站地址策略

`toolregistry.netpolicy` 在连接打开之前回答一个问题：**这个 URL 能否被拨号？**
URL 可能来自文档、管理面板请求或配置文件，而进程通常运行在信任对端网络中。
该策略会解析主机名，并拒绝所有不是全球可达单播地址的答案。

```python
from toolregistry.netpolicy import UnsafeAddressError, validate_outbound_url

validate_outbound_url("https://api.example.com/openapi.json")  # 通过
validate_outbound_url("http://127.0.0.1:8000/spec.json")       # PrivateAddressError
```

## API

| 对象 | 用途 |
|------|------|
| `validate_outbound_url(url, *, allow_private_hosts=False)` | 解析 `url` 的主机名并原样返回 `url`，否则抛出异常 |
| `validate_outbound_url_async(url, *, allow_private_hosts=False, timeout=5.0)` | 相同的检查，通过事件循环解析 |
| `resolve_outbound_url(url, *, allow_private_hosts=False)` | 相同的检查，并返回 `(url, addresses)` 及它所判定的地址 |
| `resolve_outbound_url_async(url, *, allow_private_hosts=False, timeout=5.0)` | 上者的异步版本 |
| `SCHEMES` | `frozenset({"http", "https", "ws", "wss"})` |
| `UnsafeAddressError` | 基类，是 `ValueError` 的子类 |
| `PrivateAddressError` | 子类，主机解析到非公网地址时抛出 |
| `clear_address_cache()` | 清除所有缓存的判定结果 |

### `validate_outbound_url`

```python
def validate_outbound_url(url: str, *, allow_private_hosts: bool = False) -> str: ...
```

同步版本在调用线程上解析。异步调用方应使用
`validate_outbound_url_async`，以免阻塞事件循环；两种形式共享同一个缓存。

### `resolve_outbound_url`

```python
def resolve_outbound_url(url: str, *, allow_private_hosts: bool = False) -> tuple[str, tuple[str, ...]]: ...
```

策略与 `validate_outbound_url` 完全相同；返回值还带上被判定过的地址，顺序与
解析器返回一致。能够固定连接地址的传输层——例如 `httpclient` 的
`resolve_to`——可以直接使用这些地址，而不必再解析一次主机名。那第二次解析正是
检查与拨号之间的 DNS 重绑定窗口。

```python
from toolregistry.netpolicy import resolve_outbound_url

url, addresses = resolve_outbound_url("https://api.example.com/spec.json")
# 把 addresses 交给支持固定连接地址的传输层。
```

主机是 IP 字面量时，原样作为唯一地址返回。缓存命中时返回的是当初通过检查的
地址，而不是解析器的最新答案，因此缓存窗口内的重绑定无法改写已固定的连接。
解析器返回空列表时与解析失败一样被拒绝。

与 validate 系列有一处差异：`allow_private_hosts=True` 时 resolve 系列仍会解析，
因为调用方需要地址；而 `validate_outbound_url` 在该情况下直接返回、不做任何 DNS
查询。未经检查的解析结果不会进入缓存，因此无法让后续的校验调用通过缓存放行。

### 异常

`PrivateAddressError` 带有 `addresses` 属性，按顺序保存解析器返回的全部地址。
异常消息不会写出解析后的地址：异常文本会流向客户端、日志和下游适配器，
而解析后的地址属于内部网络拓扑。需要该地址的调用方读取该属性。

两个异常类分开，是因为补救方式不同。私有地址有开关
（`allow_private_hosts=True`）；无法解析的名称、格式错误的 URL 或不支持的
scheme 没有开关。

```python
from toolregistry.netpolicy import PrivateAddressError

try:
    validate_outbound_url("http://localhost:11434")
except PrivateAddressError as exc:
    print(exc.addresses)  # ('127.0.0.1',)
```

## 拒绝范围

| 类别 | 示例 |
|------|------|
| 不支持的 scheme | `file:`、`ftp:`、缺少 scheme |
| 缺少或无法解析的主机 | `http://`、格式错误的 IPv6 字面量、非法端口 |
| 无法解析的名称 | NXDOMAIN、解析器故障、超时 |
| 回环、链路本地、未指定、组播、保留地址 | `127.0.0.1`、`::1`、`169.254.1.1`、`fe80::1`、`0.0.0.0`、`224.0.0.1` |
| 私有网段 | `10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、`fc00::/7` |
| 特殊用途转换网段 | `::/96`、`2001::/32`（Teredo）、`2002::/16`（6to4）、`64:ff9b:1::/48` |
| 其他特殊用途网段 | `192.0.0.0/24`、`192.88.99.0/24`、`198.18.0.0/15`、`240.0.0.0/4`、`100::/64`、`2001:2::/48`、`2001:10::/28`、`2001:20::/28`、`2001:db8::/32`、`3fff::/20`、`5f00::/16` |

`ipaddress.is_global` 是白名单，但它背后的 IANA 特殊用途地址表会随解释器
版本变化。上表中的网段同时被显式拒绝，因此后续的地址表变化无法悄悄放开它们。

解析器返回的每个地址都必须是公网地址。公网答案中只要有一个私有答案，整个
URL 就会被拒绝。

### NAT64 与 IPv4 映射地址

IPv4 映射地址（`::ffff:a.b.c.d`）和 NAT64 知名前缀（`64:ff9b::/96`）会到达
其低 32 位所表示的 IPv4 主机，但 `is_global` 判定的是 IPv6 前缀。若不特殊
处理，`64:ff9b::7f00:1` 看起来是公网地址，实际却到达 `127.0.0.1`。策略会
解开这两种地址，并对内嵌的 IPv4 地址重新检查。

NAT64 本地使用前缀（`64:ff9b:1::/48`）整段拒绝。RFC 8215 将 IPv4 地址放在
与部署相关的位置，因此没有固定的位段可以信任：`64:ff9b:1::808:808` 的低 32
位看起来是 `8.8.8.8`，实际内嵌目标是 `0.0.0.0`。

## 缓存

成功的检查以 `(scheme, host, port)` 为键缓存 60 秒
（`CACHE_TTL_SECONDS`）。失败从不缓存：一次 DNS 抖动不应让某个主机被锁定到
进程重启。网络变更后或测试中调用 `clear_address_cache()`。

缓存窗口同时也是 DNS 答案变化可能被忽略的时长——参见下文的约定。

## 解析超时

`validate_outbound_url_async` 用 `timeout`（默认 5.0 秒，
`RESOLVE_TIMEOUT_SECONDS`）限制解析器等待时间，超时即以
`UnsafeAddressError` 失败关闭。同步版本自身没有超时；由平台解析器决定。

## 策略适用范围

核心在每一个「根据调用方未必选择的 URL 打开连接」的位置应用该检查：

- `validate_spec_url()`、`load_openapi_spec()`、`load_openapi_spec_async()`、
  `extract_base_url_from_specs()`
- `HttpClientConfig` 和两个 base-URL 客户端
- `OpenAPISource`
- `MCPClient`、`register_mcp_tools*()`、`register(..., source="mcp")`、
  `MCPSource`
- `registry.enable_admin()`

每个入口都接受 `allow_private_hosts=True` 以访问本地或内部 API。管理面板有
自己的开关：`registry.enable_admin(allow_private_hosts=True)`；`GET /api/info`
会报告该值，当服务器拒绝私有地址时 OpenAPI 表单会显示提示。

## 策略不负责的事情

策略只负责判定，到拨号为止。它不会：

- **跟随重定向。** 在 spec 加载路径上，指向未经检查地址的 3xx 会被拒绝；目标
  可信时可用 `follow_redirects=True` 选择跟随。工具调用路径上的重定向重新
  校验记录在 #399。
- **把解析结果固定到连接上。** 连接打开时会再次解析，因此在此期间改变答案的
  域名服务器（DNS 重绑定）可以绕过检查。要堵住这个口子，需要连接层连接到
  固定地址，同时保留原始名称用于 `Host` 和 TLS SNI。
- **在跨源重定向时剥离凭据。**

获取他人提供的 URL 的调用方自行负责这些决定。

## 兼容性

`toolregistry._netpolicy` 仍可导入，并解析到相同的对象。新代码应从
`toolregistry.netpolicy` 导入。

## 另见

- [迁移到 0.20](../../guides/migrating-to-0.20.md) —— 恢复旧行为的各个开关
- [管理面板：安全性](../../admin/security.md) —— 管理面板自己的开关与限流
