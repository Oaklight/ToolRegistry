import json
import re
from typing import Dict, List, Literal, Optional
import unicodedata

import httpx
from bs4 import BeautifulSoup
from httpx import Limits, Timeout
from pydantic import BaseModel

# results_example = [
#   {
#     "url": "https://www.weather.com.cn/weather/401070101.shtml",
#     "title": "【芝加哥天气】芝加哥天气预报,天气预报一周,天气预报15天查询",
#     "content": "24日（今天）. 阴. 8℃. <3级. 25日（明天）. 阴转小雨. 15℃ ...",
#     "thumbnail": null,
#     "engine": "google",
#     "template": "default.html",
#     "parsed_url": [
#       "https",
#       "www.weather.com.cn",
#       "/weather/401070101.shtml",
#       "",
#       "",
#       ""
#     ],
#     "img_src": "",
#     "priority": "",
#     "engines": [
#       "google"
#     ],
#     "positions": [
#       1
#     ],
#     "score": 1.0,
#     "category": "general"
#   },
# ]


class WebSearchEntry(BaseModel):
    content: str
    thumbnail: Optional[str] = None
    engine: str
    template: str
    parsed_url: List[str]
    img_src: Optional[str] = None
    priority: Optional[str] = None
    engines: List[str]
    positions: List[int]
    score: float
    category: str


def _remove_emojis(text: str) -> str:
    """Remove emoji expressions from text"""
    return "".join(c for c in text if not unicodedata.category(c).startswith("So"))


def _format_text(text: str) -> str:
    """Format text content"""
    # Normalize Unicode
    text = unicodedata.normalize("NFKC", text)
    # Remove redundant whitespace (preserve newline semantics)
    # 1. Replace all non-newline whitespace characters with a single space
    text = re.sub(r"[^\S\n]+", " ", text)
    # 2. Replace multiple newlines with a single newline
    text = re.sub(r"\n+", "\n", text)
    # 3. Remove leading and trailing whitespace
    text = text.strip()
    # Remove emoji
    text = _remove_emojis(text)
    return text


def search(query: str):
    """Perform search and return results"""
    params = {
        "q": query,
        "format": "json",
        "number_of_results": 4,
    }

    # 配置HTTP客户端
    limits = Limits(max_connections=100, max_keepalive_connections=20)
    timeout = Timeout(10.0, connect=5.0)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    with httpx.Client(limits=limits, timeout=timeout) as client:
        try:
            response = client.get(
                "https://searx.perennialte.ch//search", params=params, headers=headers
            )
            response.raise_for_status()
            results = response.json().get("results", [])  # get the search results list
            return results
        except httpx.RequestError as e:
            print(f"Request error: {e}")
            return []
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code}")
            return []


def _get_content_with_jina_reader(
    url: str, return_format: Literal["markdown", "text", "html"] = "text"
) -> str:
    """
    Fetch parsed content from Jina AI for a given URL. This function is intended to be used internally.
    It sends a request to Jina AI's API to get the content of the webpage.
    If the request is successful, it returns the content.
    If the request fails, it returns an empty string.

    Args:
       url: The URL of the webpage to fetch.

    Returns:
        str: The content of the webpage or an empty string if the request fails.
    """
    try:
        headers = {
            "X-Return-Format": return_format,
            "X-Remove-Selector": "header, .class, #id",
            "X-Target-Selector": "body, .class, #id",
        }
        jina_reader_url = "https://r.jina.ai/"
        response = httpx.get(jina_reader_url + url, headers=headers, timeout=10.0)
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error [{e.response.status_code}]: {e}")
        return ""
    except Exception as e:
        print(f"Other error: {e}")
        return ""


def _get_content_with_bs4(url: str) -> str:
    """Utilizes BeautifulSoup to fetch and parse the content of a webpage.

    Args:
        url: The URL of the webpage to fetch.
    Returns:
        str: The parsed content of the webpage or an empty string if the request fails.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        response = httpx.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove unnecessary elements
        for element in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
            element.decompose()

        # Attempt to retrieve main content area
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="content")
        )

        # If no specific area is found, use the entire body
        content_source = main_content if main_content else soup.body

        if not content_source:
            return ""

        # Retrieve original text content
        return content_source.get_text(separator=" ", strip=True)

    except httpx.HTTPStatusError as e:
        print(f"HTTP Error [{e.response.status_code}]: {e}")
        return ""
    except Exception as e:
        print(f"Error parsing webpage content: {e}")
        return ""


def fetch_webpage_content(entry: WebSearchEntry, use_jina: bool = False) -> dict:
    """Retrieve complete webpage content from search result entry

    Args:
        entry: Search result dictionary containing url, title, etc.
        use_jina: Whether to use Jina Reader service

    Returns:
        dict: Dictionary containing webpage information, structured as:
        {
            "title": Webpage title,
            "url": Webpage URL,
            "content": Main content text,
            "excerpt": Summary content extracted by search engine
        }

    Raises:
        ValueError: Invalid URL or content
    """
    UNABLE_TO_FETCH_CONTENT = "Unable to fetch content"
    UNABLE_TO_FETCH_TITLE = "Unable to fetch title"

    if not entry.get("url"):
        raise ValueError("Result missing URL")

    try:
        # Retrieve webpage content
        content = ""
        if use_jina:
            content = _get_content_with_jina_reader(entry["url"])
            # Fallback to BS4 when Jina Reader returns empty
            if not content:
                content = _get_content_with_bs4(entry["url"])
        else:
            content = _get_content_with_bs4(entry["url"])

        # Retrieve title
        title = entry.get("title", UNABLE_TO_FETCH_TITLE)
        title = _format_text(title)

        # Uniformly format content
        formatted_content = (
            _format_text(content) if content else UNABLE_TO_FETCH_CONTENT
        )
        return {
            "title": title,
            "url": entry["url"],
            "content": formatted_content,
            "excerpt": entry["content"],
        }

    except Exception as e:
        print(f"Error retrieving webpage content: {e}")
        return {
            "title": result.get("title", UNABLE_TO_FETCH_TITLE),
            "url": result["url"],
            "content": UNABLE_TO_FETCH_CONTENT,
            "excerpt": UNABLE_TO_FETCH_CONTENT,
        }


# Example usage
if __name__ == "__main__":
    result = search("Chicago weather today")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试新函数
    if result:
        try:
            webpage = fetch_webpage_content(
                result[0],
            )
            print("\nWebpage information:")
            print(f"Title: {webpage['title']}")
            print(f"URL: {webpage['url']}")
            print(f"\nSummary: {webpage['excerpt']}")
            print("\nFull content:")
            print(webpage["content"] + "...")
        except Exception as e:
            print(f"Failed to retrieve webpage content: {e}")
