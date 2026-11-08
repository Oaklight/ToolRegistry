# 迁移到 0.20

本版本改变了出站请求可到达的范围、OpenAPI 加载器抓取与限制文档的方式，以及工具响应会被缓冲多少内容。每项变更都提供了显式开关，在仍然安全的前提下恢复旧行为。

## 出站地址策略

所有出站请求现在都会在建立连接前解析主机，并拒绝回环、链路本地、私有、组播与保留地址；无法解析的名称同样拒绝。成功结果缓存 60 秒，失败不缓存。

该策略覆盖 `validate_spec_url()`、`load_openapi_spec()`、`load_openapi_spec_async()`、`extract_base_url_from_specs()`、`HttpClientConfig`、两个 base URL 客户端、`OpenAPISource`、`MCPClient`、`register_mcp_tools*()`、`register(..., source="mcp")`、`MCPSource` 与 `registry.enable_admin()`。

本机或内网 API 需要显式开启：

```python
# 之前：主机原样使用
config = HttpClientConfig(base_url="http://localhost:11434")

# 之后：非公网主机会抛 UnsafeAddressError
config = HttpClientConfig(base_url="http://localhost:11434", allow_private_hosts=True)
```

其他入口使用同一个开关：

```python
spec = load_openapi_spec(
    "http://127.0.0.1:8000/openapi.json",
    allow_private_hosts=True,
)

registry.register(..., source="openapi", allow_private_hosts=True)
registry.register(..., source="mcp", allow_private_hosts=True)
```

管理面板有自己的开关：以 `registry.enable_admin(allow_private_hosts=True)` 启动，预览与注册才能访问本机 API。`GET /api/info` 以 `allow_private_hosts` 返回该值；服务器拒绝私有地址时，OpenAPI 表单会给出提示。

## 重定向

`load_openapi_spec()`、`load_openapi_spec_async()` 与 `determine_urls()` 默认不再跟随重定向。下一跳无法按出站策略检查，且 vendored 客户端不暴露 `Location`，因此 3xx 会被拒绝，错误信息不会回显重定向目标，只要求调用方改用最终 URL。

```python
# 之前：302 会被跟随到无人校验的地址
spec = load_openapi_spec("https://api.example.com/openapi.json")

# 之后：直接传入最终 URL……
spec = load_openapi_spec("https://api.example.com/v2/openapi.json")

# ……或在目标可信时显式开启
spec = load_openapi_spec("https://api.example.com/openapi.json", follow_redirects=True)
```

工具调用仍会跟随重定向，因为 vendored HTTP 客户端无法暴露每一跳供校验；调用路径的重定向复检记录在 #399。

## 规范大小与深度

下载的文档默认最多缓冲 10 MiB（`DEFAULT_MAX_SPEC_BYTES`），嵌套最多 100 层容器（`DEFAULT_MAX_SPEC_DEPTH`）。声明的 `Content-Length` 超限时会在读取正文前拒绝，无上限的流会在达到限制时中止。解析器递归溢出会抛出 `SpecTooDeepError`，而不是通用的 `ValueError`。

```python
# 之前：不限制大小与深度
spec = load_openapi_spec(url)

# 之后：文档确实更大时调高预算
spec = load_openapi_spec(url, max_bytes=32 * 1024 * 1024, max_depth=200)
```

## 工具响应大小

OpenAPI 工具调用会缓冲响应，因此默认上限为 10 MiB（`DEFAULT_MAX_TOOL_RESPONSE_BYTES`，可从 `toolregistry.utils` 导入）。超过上限会抛出 `ResponseTooLargeError`，该异常由 `toolregistry.errors` 重新导出。

```python
# 之前：无论多大都会完整缓冲响应体
config = HttpClientConfig(base_url=BASE)

# 之后：调高上限……
config = HttpClientConfig(base_url=BASE, max_response_size=64 * 1024 * 1024)

# ……或对确实需要无上限读取的工具关闭限制
config = HttpClientConfig(base_url=BASE, max_response_size=None)
```

## 本地规范文件

`load_openapi_spec()` 与 `load_openapi_spec_async()` 过去会把任何无 scheme 或 `file` scheme 的 URI 当作本地文件读取，因此把别人提供的位置传进来的调用方可能被诱导读取任意文件。现在两者对本地路径与 `file://` URI 在任何 I/O 之前抛出 `ValueError`。

```python
# 之前
spec = load_openapi_spec("./openapi.json")

# 之后
spec = load_openapi_spec("./openapi.json", allow_local_files=True)
```

管理面板不受影响：它的 `spec_url` 此前已限定为 http(s)。
