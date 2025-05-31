import time
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional

import httpx
from loguru import logger

from .filter import filter_search_results
from .headers import HEADERS_DEFAULT, TIMEOUT_DEFAULT
from .websearch import WebSearchGeneral


class _WebSearchEntrySearXNG(dict):
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


class WebSearchSearXNG(WebSearchGeneral):
    """WebSearchSearXNG provides a unified interface for performing web searches and processing results
    through a SearXNG instance. It handles search queries, result filtering, and content extraction.

    Features:
    - Performs web searches using SearXNG instance
    - Filters results by relevance score threshold
    - Extracts and cleans webpage content using multiple methods (BeautifulSoup/Jina Reader)
    - Parallel processing of result fetching
    - Automatic emoji removal and text normalization

    Examples:
        >>> from toolregistry.hub.websearch_searxng import WebSearchSearXNG
        >>> searcher = WebSearchSearXNG("http://localhost:8080")
        >>> results = searcher.search("python web scraping", number_results=3)
        >>> for result in results:
        ...     print(result["title"])
    """

    def __init__(
        self,
        searxng_base_url: str,
        proxy: Optional[str] = None,
    ):
        """Initialize WebSearchSearXNG with configuration parameters.
        Args:
           searxng_base_url (str): Base URL for the SearXNG instance (e.g. "http://localhost:8080").
           proxy (Optional[str]): Proxy URL for HTTP requests.
        """
        self.searxng_base_url: str = searxng_base_url.rstrip("/")
        if not self.searxng_base_url.endswith("/search"):
            self.searxng_base_url += "/search"  # Ensure the URL ends with /search

        self.proxy: Optional[str] = proxy if proxy else None

    def search(
        self,
        query: str,
        number_results: int = 5,
        threshold: float = 0.2,
        timeout: Optional[float] = None,
    ) -> List[Dict[str, str]]:
        """Perform search and return results.

        Args:
            query (str): The search query. Boolean operators like AND, OR, NOT can be used if needed.
            number_results (int, optional): The maximum number of results to return. Defaults to 5.
            threshold (float, optional): Minimum score threshold for results [0-1.0]. Defaults to 0.2.
            timeout (float, optional): Request timeout in seconds. Defaults to TIMEOUT_DEFAULT (10). Usually not needed.

        Returns:
            List[Dict[str, str]]: A list of enriched search results. Each dictionary contains:
            - 'title': The title of the search result.
            - 'url': The URL of the search result.
            - 'content': The content of the search result.
            - 'excerpt': The excerpt of the search result.
        """
        try:
            results = self._meta_search_searxng(
                query,
                num_results=number_results * 2,
                proxy=self.proxy,
                timeout=timeout,
                searxng_base_url=self.searxng_base_url,
            )

            scored_results = [
                entry for entry in results if entry.get("score", 0) >= threshold
            ]

            start_time = time.time()
            filtered_results = filter_search_results(
                [dict(entry) for entry in scored_results]
            )
            if len(filtered_results) > number_results:
                filtered_results = filtered_results[:number_results]
            elapsed_time = time.time() - start_time
            logger.debug(f"filter_search_results took {elapsed_time:.4f} seconds")

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

    @staticmethod
    def _meta_search_searxng(
        query,
        num_results=10,
        proxy: Optional[str] = None,
        timeout: Optional[float] = 5,
        searxng_base_url: str = "http://localhost:8080/search",
    ) -> List[_WebSearchEntrySearXNG]:
        """
        Perform a search using SearXNG and return the results.
        """
        response = httpx.get(
            searxng_base_url,
            params={
                "q": query,
                "format": "json",
            },
            headers=HEADERS_DEFAULT,
            proxy=proxy,
            timeout=timeout or TIMEOUT_DEFAULT,
        )
        response.raise_for_status()
        results = response.json().get("results", [])

        results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)
        if len(results) > num_results:
            # Fetch additional results if needed
            results = results[:num_results]

        return results


WebSearchSearxng = WebSearchSearXNG  # Alias for compatibility with existing code using WebSearchSearxng

if __name__ == "__main__":
    import json
    import os

    SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")

    search_tool = WebSearchSearXNG(SEARXNG_URL)
    results = search_tool.search("Barcelona weather today", 5)
    for result in results:
        print(json.dumps(result, indent=2, ensure_ascii=False))
