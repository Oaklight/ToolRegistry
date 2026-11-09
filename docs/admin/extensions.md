# 管理面板扩展

扩展为管理面板增加一个分区。它提供一个导航项、一个面板、一个资源目录，并可在 `/ext/<name>` 下注册 HTTP 路由。认证、页面外壳与资源路径仍由面板负责，扩展不接触这些部分。

契约带版本号。本版本只提供版本 1。

## 声明扩展

扩展是一个带有下列属性与 `register` 方法的对象。

| 属性 | 必需 | 含义 |
|------|------|------|
| `name` | 是 | 匹配 `^[a-z][a-z0-9_-]*$` 的小写标识符。它同时是 URL 段 `/ext/<name>` 与资源目录的键。 |
| `title` | 是 | 导航标签的多语言映射，例如 `{"en": "Clock", "zh": "时钟"}`。 |
| `assets` | 有标签页时必需 | 磁盘目录，`entry` 与 `styles` 从中读取。声明 `nav` 或任何资源时必须提供。 |
| `entry` | 有标签页时必需 | `assets/ext/<name>/` 下的浏览器模块路径，以 `.js` 结尾。存在 `nav` 时必需。 |
| `requires_api` | 是 | 扩展面向的契约版本，必须等于 `ADMIN_EXTENSION_API`（`1`）。 |
| `styles` | 有标签页时必需 | `assets/ext/<name>/` 下 `.css` 路径的序列。需要 `nav`。 |
| `icon` | 否 | 导航项的 SVG 标记。默认为网格图标。 |
| `nav` | 否 | 映射，可含 `group` 翻译键与整数 `order`（默认 `100`）。 |
| `register` | 是 | 以 `AdminContext` 调用一次。 |

`name`、`title`、`requires_api` 与 `register` 在监听器启动前校验。违反契约会抛出带扩展名的 `AdminExtensionError`，`AdminServer.start()` 失败；面板不会运行只挂载了一半的扩展。

只提供 HTTP 路由的扩展可省略 `nav`、`assets`、`entry` 与 `styles`。其路由照常挂载，`GET /api/extensions` 报告 `"nav": null` 与 `"entry": null`，面板不为它显示标签页。

`styles` 需要 `nav`：加载器会完全跳过纯 API 扩展，未声明标签页的样式表永远不会被应用，因此启动时会被拒绝。

不以 `assets/ext/<name>/` 开头、含点段、或后缀不在 `.css` / `.js` 之内的路径一律拒绝。

## 注册路由

`register` 收到一个 `AdminContext`。它的方法在 `/ext/<name>` 下注册处理器：

```python
from pathlib import Path

from toolregistry import ADMIN_EXTENSION_API, AdminServer, ToolRegistry


class ClockExtension:
    name = "clock"
    title = {"en": "Clock", "zh": "时钟"}
    entry = "assets/ext/clock/main.js"
    styles = ("assets/ext/clock/style.css",)
    requires_api = ADMIN_EXTENSION_API
    assets = Path("/srv/toolregistry/extensions/clock/static")
    nav = {"group": "utilities", "order": 20}

    def register(self, ctx):
        ctx.get("/now", self.now)
        ctx.get("/zones/<path:zone>", self.zone)

    def now(self, request):
        return {"now": "tick"}

    def zone(self, request, zone):
        return {"zone": zone}


registry = ToolRegistry()
server = AdminServer(registry, port=8081, extensions=[ClockExtension()])
info = server.start()
```

辅助方法为 `ctx.get`、`ctx.post`、`ctx.put`、`ctx.patch` 与 `ctx.delete`。每个方法接收路径与处理器；也支持装饰器写法：

```python
@ctx.get("/status")
def status(request):
    return {"ok": True}
```

处理器遵循面板的约定：先接收请求，再接收路径参数，返回可 JSON 序列化的值。同步处理器在工作线程中运行。上下文还提供 `registry`、`api_prefix`、`api_url(path)` 与 `asset_url(path)`。

同一方法加同一路径注册两次会抛出 `AdminExtensionError`。

## 清单

`GET /api/extensions` 按声明顺序返回所有已挂载扩展：

```json
{
  "api_version": 1,
  "extensions": [
    {
      "name": "clock",
      "title": {"en": "Clock", "zh": "时钟"},
      "icon": null,
      "nav": {"group": "utilities", "order": 20},
      "entry": "assets/ext/clock/main.js",
      "styles": ["assets/ext/clock/style.css"],
      "api_prefix": "/ext/clock",
      "requires_api": 1
    }
  ]
}
```

该端点与管理面板其余部分使用相同的认证。仅提供 API 的扩展以 `"nav": null` 与 `"entry": null` 出现。

`nav.group` 是翻译键而非显示标签：字典定义了 `group.<key>` 时页面外壳渲染译文，其次回退到外壳自身的 `nav.<key>`，因此扩展可复用 `manage` 等内置分区标签；两者都未定义时显示键本身。分组键与 `name` 使用相同的小写字符集。

## 浏览器模块

页面外壳获取清单，添加导航项与面板，然后把 `entry` 作为 ES 模块导入。模块导出 `register`，也可导出 `unmount`：

```javascript
// assets/ext/clock/main.js
export async function register({ container, api, i18n, manifest }) {
    const heading = document.createElement('h2');
    heading.textContent = manifest.title[i18n.lang] || manifest.title.en;
    container.appendChild(heading);

    const value = document.createElement('p');
    container.appendChild(value);

    const tick = async () => {
        const data = await api.get('/now');
        value.textContent = data.now;
    };
    await tick();
}

export function unmount() {
    // 释放 register() 创建的定时器、套接字或监听器。
}
```

`register` 收到：

- `container`：面板的内容元素。它是空的，归该扩展所有。
- `api`：访问该扩展路由的客户端。`api.get(path)`、`api.post(path, body)`、`api.put`、`api.patch`、`api.delete` 与 `api.request(path, options)` 都会加上扩展前缀并使用面板的认证。`api.url(path)` 只返回 URL，不发送请求。
- `i18n`：`{lang, t(key, params)}`。`t` 读取面板共享的翻译表；扩展自有文案可直接按 `lang` 选择。
- `manifest`：`GET /api/extensions` 中的对应条目。

`unmount` 可选。加载器移除扩展时会调用它，应释放 `register` 启动的一切。

切换语言时，导航项会按 `title` 重新标注，但面板不会重新渲染扩展内容。扩展若需要翻译自身文本，应在渲染时读取 `i18n.lang`，并在语言变化时自行刷新。

模块在加载或注册时抛错不会影响面板：错误记录到控制台，该扩展的导航项、面板与样式表会被移除。

## 资源

`assets` 目录下的文件通过 `/assets/ext/<name>/...` 提供。只提供 `.css` 与 `.js`，请求路径会检查点段，解析后的文件必须位于该目录内，因此符号链接无法逃逸。

启用 UI 时，扩展资源与页面外壳共享认证豁免：浏览器必须先加载面板脚本，才能弹出令牌输入框。处理器只提供已声明且内容类型在白名单内的文件。因而即使面板启用了令牌，扩展资源也对任何能访问面板端口的人公开。不要在其中放密钥。

## 安全与版本

- **单一认证级别。** 扩展路由继承面板策略，没有按扩展区分的令牌或角色。
- **跨站防护同样生效。** 对 `/ext/...` 的状态变更请求与 `/api/...` 遵循相同的来源、`Sec-Fetch-Site` 与 JSON 内容类型规则。
- **版本握手。** `requires_api` 在服务端启动时校验，浏览器再对照 `api_version` 校验。不匹配会拒绝该扩展并在消息中给出扩展名，绝不会静默挂载。
- **信任。** 扩展是运维方安装的代码。其浏览器模块以面板权限运行，`icon` 字符串按 SVG 标记插入。扩展没有沙箱，因此面板的 XSS 边界只取决于扩展自身的正确性。只安装你信任的扩展。
