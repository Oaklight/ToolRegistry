# Fetch - Simple Web Content Extraction Tool

```{note}
Since v0.4.11, the Fetch tool has been spun out of websearch, exposing only the Fetch class, focusing on the automatic extraction of web page main content.
```

The Fetch tool is designed to scrape the main content from a specified URL. It has a minimal interface and automatically handles common web page structures and encodings without requiring additional configuration. It is suitable for scenarios where you need to quickly retrieve web page main text.

## Key Features

- Simply provide a URL to automatically scrape and extract the main web page content
- Automatically handles common encodings, removes scripts/styles/navigation, etc., irrelevant content
- Built-in exception handling returns a message when fetching fails
- Supports optional timeout parameter

## Interface Description

- `Fetch.fetch_content(url: str, timeout: Optional[float] = None) -> str`

  - `url`: The URL of the target web page (required)
  - `timeout`: Request timeout in seconds (optional, default is 10)

Returns the extracted main content string. If fetching fails, "Unable to fetch content" is returned.

## Example Usage

```python
from toolregistry.hub import Fetch

# Basic usage
content = Fetch.fetch_content("https://example.com/article/123")
print(content)

# Set timeout
content = Fetch.fetch_content("https://example.com/article/123", timeout=5)
print(content)
```

## Applicable Scenarios

- Quickly retrieve web page main text
- Collaborate with the WebSearch tool for batch content extraction from search results
- Suitable for web content extraction with a minimal interface and no complex configuration
