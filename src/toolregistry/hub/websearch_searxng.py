import re
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Literal, Optional

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from loguru import logger

_UNABLE_TO_FETCH_CONTENT = "Unable to fetch content"
_UNABLE_TO_FETCH_TITLE = "Unable to fetch title"
HEADERS_DEFAULT = {"User-Agent": UserAgent(platforms="mobile").random}
TIMEOUT_DEFAULT = 10.0


class _WebSearchSearxngEntry(dict):
    """Search result entry model with type validation."""

    def __init__(self, **data):
        super().__init__(**data)

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
    """WebSearchSearxng provides a unified interface for performing web searches and processing results
    through a SearxNG instance. It handles search queries, result filtering, and content extraction.

    Features:
    - Performs web searches using SearxNG instance
    - Filters results by relevance score threshold
    - Extracts and cleans webpage content using multiple methods (BeautifulSoup/Jina Reader)
    - Parallel processing of result fetching
    - Automatic emoji removal and text normalization

    Attributes:
        searxng_base_url (str): Base URL for the SearxNG instance (e.g. "http://localhost:8080").
        timeout (float): Timeout for HTTP requests in seconds. Default is 10.
        headers (Dict[str, str], Optional): HTTP headers for requests.

    Examples:
        >>> from toolregistry.hub.websearch_searxng import WebSearchSearxng
        >>> searcher = WebSearchSearxng("http://localhost:8080")
        >>> results = searcher.search("python web scraping", number_of_results=3)
        >>> for result in results:
        ...     print(result["title"])
    """

    @staticmethod
    def _remove_emojis(text: str) -> str:
        """Remove emoji expressions from text.

        Args:
            text (str): The input text.

        Returns:
            str: Text with emojis removed.
        """
        return "".join(c for c in text if not unicodedata.category(c).startswith("So"))

    @staticmethod
    def _format_text(text: str) -> str:
        """Format text content.

        Args:
            text (str): The input text.

        Returns:
            str: Formatted text.
        """
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n+", "\n", text)
        text = text.strip()
        text = WebSearchSearxng._remove_emojis(text)
        return text

    @staticmethod
    def _get_content_with_jina_reader(
        url: str,
        return_format: Literal["markdown", "text", "html"] = "text",
        timeout: Optional[float] = None,
    ) -> str:
        """Fetch parsed content from Jina AI for a given URL.

        Args:
            url (str): The URL to fetch content from.
            return_format (Literal["markdown", "text", "html"], optional): The format of the returned content. Defaults to "text".
            timeout (Optional[float], optional): Timeout for the HTTP request. Defaults to TIMEOUT_DEFAULT.

        Returns:
            str: Parsed content from Jina AI.
        """
        try:
            headers = {
                "X-Return-Format": return_format,
                "X-Remove-Selector": "header, .class, #id",
                "X-Target-Selector": "body, .class, #id",
            }
            jina_reader_url = "https://r.jina.ai/"
            response = httpx.get(
                jina_reader_url + url,
                headers=headers,
                timeout=timeout or TIMEOUT_DEFAULT,
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.debug(f"HTTP Error [{e.response.status_code}]: {e}")
            return ""
        except Exception as e:
            logger.debug(f"Other error: {e}")
            return ""

    @staticmethod
    def _get_content_with_bs4(
        url: str,
        timeout: Optional[float] = None,
    ) -> str:
        """Utilizes BeautifulSoup to fetch and parse the content of a webpage.

        Args:
            url (str): The URL of the webpage.
            headers (Optional[Dict[str, str]]): HTTP headers to be sent with the request. Defaults to HEADERS_DEFAULT.
            timeout (Optional[float]): Timeout for the HTTP request. Defaults to TIMEOUT_DEFAULT.

        Returns:
            str: Parsed text content of the webpage.
        """
        try:
            response = httpx.get(
                url,
                headers=HEADERS_DEFAULT,
                timeout=timeout or TIMEOUT_DEFAULT,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup(
                ["script", "style", "nav", "footer", "iframe", "noscript"]
            ):
                element.decompose()
            main_content = (
                soup.find("main")
                or soup.find("article")
                or soup.find("div", {"class": "content"})
            )
            content_source = main_content if main_content else soup.body
            if not content_source:
                return ""
            return content_source.get_text(separator=" ", strip=True)
        except httpx.HTTPStatusError as e:
            logger.debug(f"HTTP Error [{e.response.status_code}]: {e}")
            return ""
        except Exception as e:
            logger.debug(f"Error parsing webpage content: {e}")
            return ""

    def __init__(
        self,
        searxng_base_url: str,
    ):
        """Initialize WebSearchSearxng with configuration parameters."""
        self.searxng_base_url = searxng_base_url.rstrip("/")
        if not self.searxng_base_url.endswith("/search"):
            self.searxng_base_url += "/search"  # Ensure the URL ends with /search

        self._headers = HEADERS_DEFAULT

    def extract(self, url: str, timeout: Optional[float] = None) -> str:
        """Extract content from a given URL using available methods.

        Args:
            url (str): The URL to extract content from.
            timeout (float, optional): Request timeout in seconds. Defaults to TIMEOUT_DEFAULT (10). Usually not needed.

        Returns:
            str: Extracted content from the URL, or empty string if extraction fails.
        """
        # First try BeautifulSoup method
        content = self._get_content_with_bs4(url, timeout=timeout or TIMEOUT_DEFAULT)
        if not content:
            # Fallback to Jina Reader if BeautifulSoup fails
            content = self._get_content_with_jina_reader(
                url, timeout=timeout or TIMEOUT_DEFAULT
            )

        formatted_content = (
            WebSearchSearxng._format_text(content)
            if content
            else _UNABLE_TO_FETCH_CONTENT
        )
        return formatted_content

    def _fetch_webpage_content(self, entry: _WebSearchSearxngEntry) -> dict:
        """Retrieve complete webpage content from search result entry.

        Args:
            entry (_WebSearchSearxngEntry): The search result entry.

        Returns:
            Dict[str, str]: A dictionary containing the title, URL, content, and excerpt of the webpage.
        """
        url = entry["url"]
        if not url:
            raise ValueError("Result missing URL")

        try:
            content = self.extract(url)
        except Exception as e:
            content = _UNABLE_TO_FETCH_CONTENT
            logger.debug(f"Error retrieving webpage content: {e}")

        return {
            "title": entry.get("title", _UNABLE_TO_FETCH_TITLE),
            "url": url,
            "content": content,
            "excerpt": _UNABLE_TO_FETCH_CONTENT,
        }

    def search(
        self,
        query: str,
        number_of_results: int = 5,
        threshold: float = 0.2,
        timeout: Optional[float] = None,
    ) -> List[Dict[str, str]]:
        """Perform search and return results.

        Args:
            query (str): The search query. Boolean operators like AND, OR, NOT can be used if needed.
            number_of_results (int, optional): The maximum number of results to return. Defaults to 5.
            threshold (float, optional): Minimum score threshold for results [0-1.0]. Defaults to 0.2.
            timeout (float, optional): Request timeout in seconds. Defaults to TIMEOUT_DEFAULT (10). Usually not needed.

        Returns:
            List[Dict[str, str]]: A list of enriched search results. Each dictionary contains:
                - 'title': The title of the search result.
                - 'url': The URL of the search result.
                - 'content': The content of the search result.
                - 'excerpt': The excerpt of the search result.
        """
        params = {"q": query, "format": "json"}
        try:
            response = httpx.get(
                self.searxng_base_url,
                params=params,
                headers=self._headers,
                timeout=timeout or TIMEOUT_DEFAULT,
            )
            response.raise_for_status()
            results = response.json().get("results", [])

            filtered_results = [
                entry for entry in results if entry.get("score", 0) >= threshold
            ]
            filtered_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            if len(filtered_results) > number_of_results:
                filtered_results = filtered_results[:number_of_results]

            with ProcessPoolExecutor() as executor:
                enriched_results = list(
                    executor.map(
                        self._fetch_webpage_content,
                        filtered_results,
                    )
                )
            return enriched_results
        except httpx.RequestError as e:
            logger.debug(f"Request error: {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.debug(f"HTTP error: {e.response.status_code}")
            return []


if __name__ == "__main__":
    import json
    import os

    SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")

    search_tool = WebSearchSearxng(SEARXNG_URL)
    results = search_tool.search("Barcelona weather today", 5)
    for result in results:
        print(json.dumps(result, indent=2, ensure_ascii=False))
