import atexit
import re
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from typing import List, Literal, Optional

import httpx
from bs4 import BeautifulSoup
from httpx import Limits, Timeout
from pydantic import BaseModel


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


class WebSearchSearxng:
    """WebSearchSearxng provides a unified interface for performing web searches and processing results."""

    @staticmethod
    def _remove_emojis(text: str) -> str:
        """Remove emoji expressions from text"""
        return "".join(c for c in text if not unicodedata.category(c).startswith("So"))

    @staticmethod
    def _format_text(text: str) -> str:
        """Format text content"""
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n+", "\n", text)
        text = text.strip()
        text = WebSearchSearxng._remove_emojis(text)
        return text

    @staticmethod
    def _get_content_with_jina_reader(
        url: str, return_format: Literal["markdown", "text", "html"] = "text"
    ) -> str:
        """Fetch parsed content from Jina AI for a given URL."""
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

    @staticmethod
    def _get_content_with_bs4(url: str) -> str:
        """Utilizes BeautifulSoup to fetch and parse the content of a webpage."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
            }
            response = httpx.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup(
                ["script", "style", "nav", "footer", "iframe", "noscript"]
            ):
                element.decompose()
            main_content = (
                soup.find("main") or soup.find("article") or soup.find("div", "content")
            )
            content_source = main_content if main_content else soup.body
            if not content_source:
                return ""
            return content_source.get_text(separator=" ", strip=True)
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error [{e.response.status_code}]: {e}")
            return ""
        except Exception as e:
            print(f"Error parsing webpage content: {e}")
            return ""

    @staticmethod
    def _fetch_webpage_content(entry: dict) -> dict:
        """Retrieve complete webpage content from search result entry."""
        UNABLE_TO_FETCH_CONTENT = "Unable to fetch content"
        UNABLE_TO_FETCH_TITLE = "Unable to fetch title"

        if not entry.get("url"):
            raise ValueError("Result missing URL")

        try:
            # Attempt to fetch content with BeautifulSoup first
            content = WebSearchSearxng._get_content_with_bs4(entry["url"])
            if not content:
                # If BeautifulSoup fails, try with Jina Reader as a fallback
                content = WebSearchSearxng._get_content_with_jina_reader(entry["url"])

            title = entry.get("title", UNABLE_TO_FETCH_TITLE)
            title = WebSearchSearxng._format_text(title)
            formatted_content = (
                WebSearchSearxng._format_text(content)
                if content
                else UNABLE_TO_FETCH_CONTENT
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
                "title": entry.get("title", UNABLE_TO_FETCH_TITLE),
                "url": entry["url"],
                "content": UNABLE_TO_FETCH_CONTENT,
                "excerpt": UNABLE_TO_FETCH_CONTENT,
            }

    def __init__(
        self,
        searxng_base_url: str,
        threshold: float = 0.2,
        timeout: float = 10.0,
        max_connections: int = 10,
        headers: Optional[dict] = None,
    ):
        """Initialize WebSearchSearxng with configuration parameters."""
        self.searxng_base_url = searxng_base_url.rstrip("/")
        if not self.searxng_base_url.endswith("/search"):
            self.searxng_base_url += "/search"  # Ensure the URL ends with /search

        self.threshold = threshold

        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        # Initialize httpx client with connection pool
        limits = Limits(max_connections=max_connections, max_keepalive_connections=20)
        self.client = httpx.Client(
            headers=self.headers, limits=limits, timeout=Timeout(timeout, connect=5.0)
        )

        atexit.register(self._shutdown_client)

    def _shutdown_client(self):
        """Close the httpx client"""
        if hasattr(self, "client"):
            self.client.close()

    def search(self, query: str, number_of_results: int = 5):
        """Perform search and return results"""
        params = {"q": query, "format": "json"}
        try:
            response = self.client.get(
                self.searxng_base_url,
                params=params,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            filtered_results = [
                entry for entry in results if entry.get("score", 0) >= self.threshold
            ]
            filtered_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            if len(filtered_results) > number_of_results:
                filtered_results = filtered_results[:number_of_results]

            with ProcessPoolExecutor() as executor:
                enriched_results = list(
                    executor.map(
                        WebSearchSearxng._fetch_webpage_content,
                        filtered_results,
                    )
                )
            return enriched_results
        except httpx.RequestError as e:
            print(f"Request error: {e}")
            return []
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code}")
            return []


if __name__ == "__main__":
    import json
    import os

    SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")

    search_tool = WebSearchSearxng(SEARXNG_URL)
    results = search_tool.search("巴塞罗那今日天气", 5)
    for result in results:
        print(json.dumps(result, indent=2, ensure_ascii=False))
