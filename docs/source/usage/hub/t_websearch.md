# WebSearch - Web search and content extraction via multiple engines

```{note}
Refined in version: v0.4.6.post1 <br>
New in version: 0.4.6
```

Provides web search (`search`) and content extraction (`extract`) functionality through multiple search engines.

Available engines:

- **SearxNG**: Self-hosted meta search engine
- **Google**: Google search API (No API key required)

**Common Configuration**:

- `timeout`: Request timeout in seconds (default: 10.0)

**SearxNG Specific**:

- `searxng_base_url`: URL of SearxNG instance (e.g. "<http://localhost:8080>")
- Proxy support: HTTP/HTTPS/SOCKS5 proxies can be configured during initialization
- Note: the searxng instance needs to enable `json` format in `settings.yml`:

    ```yaml
    search:
    formats:
        - html
        - json # add this line
    ```

**Google Search Specific**:

- No API key required
- Proxy support: HTTP/HTTPS/SOCKS5 proxies can be configured during initialization

Example:

```python
from toolregistry.hub import WebSearchSearxng, WebSearchGoogle

# Using SearxNG
searx_tool = WebSearchSearxng(searxng_base_url="http://localhost:8080")
results = searx_tool.search(query="Python web scraping", number_results=3)
extracted = searx_tool.extract(url=results[0]['url'])

# Using Google
google_tool = WebSearchGoogle()
results = google_tool.search(query="Python web scraping", number_results=3)
```
