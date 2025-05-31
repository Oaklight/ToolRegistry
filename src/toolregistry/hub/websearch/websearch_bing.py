import time
from concurrent.futures import ProcessPoolExecutor
from time import sleep
from typing import Dict, Generator, List, Optional, Set

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from .filter import filter_search_results
from .headers import HEADERS_LYNX, TIMEOUT_DEFAULT
from .websearch import WebSearchGeneral


class _WebSearchEntryBing(dict):
    """Internal class for representing Bing search results"""

    def __init__(self, **data):
        super().__init__(**data)

    url: str
    title: str
    content: str


class WebSearchBing(WebSearchGeneral):
    """WebSearchBing provides a unified interface for performing web searches on Bing.
    It handles search queries and result processing.

    Features:
    - Performs web searches using Bing
    - Returns formatted results with title, URL and description
    - Supports proxy settings

    Examples:
        >>> from toolregistry.hub.websearch_bing import WebSearchBing
        >>> searcher = WebSearchBing()
        >>> results = searcher.search("python web scraping", number_results=3)
        >>> for result in results:
        ...     print(result["title"])
    """

    def __init__(
        self,
        bing_base_url: str = "https://www.bing.com",
        proxy: Optional[str] = None,
    ):
        """Initialize WebSearchBing with configuration parameters.

        Args:
            bing_base_url (str): Base URL for the Bing search. Defaults to "https://www.bing.com".
            proxy: Optional proxy server URL (e.g. "http://proxy.example.com:8080")
        """
        self.bing_base_url = bing_base_url.rstrip("/")
        if not self.bing_base_url.endswith("/search"):
            self.bing_base_url += "/search"  # Ensure the URL ends with /search

        self.proxy: Optional[str] = proxy if proxy else None

    def search(
        self,
        query: str,
        number_results: int = 5,
        threshold: float = 0.2,  # Not used in this implementation, kept for compatibility.
        timeout: Optional[float] = None,
    ) -> List[Dict[str, str]]:
        """Perform search and return results.

        Args:
            query: The search query.
            number_results: The maximum number of results to return. Default is 5.
            timeout: Optional timeout override in seconds.

        Returns:
            List of search results, each containing:
                - 'title': The title of the search result
                - 'url': The URL of the search result
                - 'content': The description/content from Bing
                - 'excerpt': Same as content (for compatibility with WebSearchSearXNG)
        """
        try:
            results = WebSearchBing._meta_search_bing(
                query,
                num_results=number_results * 2,
                proxy=self.proxy,
                timeout=timeout or TIMEOUT_DEFAULT,
                bing_base_url=self.bing_base_url,
            )

            start_time = time.time()
            filtered_results = filter_search_results([dict(entry) for entry in results])
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
    def _meta_search_bing(
        query,
        num_results=10,
        proxy: Optional[str] = None,
        sleep_interval: float = 0,
        timeout: float = 5,
        start_num: int = 0,
        bing_base_url: str = "https://www.bing.com/search",
    ) -> List[_WebSearchEntryBing]:
        """Search the Bing search engine"""
        results = []
        fetched_results = 0
        fetched_links: Set[str] = set()

        # Create a persistent client with connection pooling
        with httpx.Client(
            proxy=proxy,
            headers=HEADERS_LYNX,
            timeout=timeout,
        ) as client:
            offset = start_num
            while fetched_results < num_results:
                response = client.get(
                    url=bing_base_url,
                    params={
                        "q": query,
                        "count": min(10, num_results - fetched_results),
                        "first": offset + 1,
                        "FORM": "PERE",
                    },
                    cookies={
                        "CONSENT": "PENDING+987",
                    },
                )
                response.raise_for_status()

                batch_entries = list(
                    WebSearchBing._parse_bing_entries(
                        response.text, fetched_links, num_results - fetched_results
                    )
                )
                if len(batch_entries) == 0:
                    break

                fetched_results += len(batch_entries)
                results.extend(batch_entries)

                offset += len(batch_entries)
                sleep(sleep_interval)

        return results

    @staticmethod
    def _parse_bing_entries(
        html: str, fetched_links: Set[str], num_results: int
    ) -> Generator[_WebSearchEntryBing, None, None]:
        """Parse HTML content from Bing search results."""
        soup = BeautifulSoup(html, "html.parser")
        result_block = soup.find_all("li", class_="b_algo")
        new_results = 0

        for result in result_block:
            if new_results >= num_results:
                break

            # Skip non-Tag elements
            if not hasattr(result, "find"):
                continue

            link_tag = result.find("a", href=True)
            # Skip non-Tag elements
            if not link_tag or not hasattr(link_tag, "find"):
                continue

            h2_tag = result.find("h2")
            link_tag = h2_tag.find("a") if h2_tag else None
            caption = result.find("div", class_="b_caption")
            description_tag = caption.find("p") if caption else None

            if not (link_tag and h2_tag and description_tag):
                continue

            try:
                link = link_tag["href"]
                if link in fetched_links:
                    continue

                fetched_links.add(link)
                title = h2_tag.text if h2_tag else ""
                description = description_tag.text if description_tag else ""
                new_results += 1

                yield _WebSearchEntryBing(
                    title=title,
                    url=link,
                    content=description,
                )
            except (AttributeError, KeyError, TypeError) as e:
                logger.debug(f"Error parsing search result: {e}")
                continue


if __name__ == "__main__":
    import json

    # Example usage
    searcher = WebSearchBing()
    results = searcher.search("巴塞罗那今日天气", 5)
    for result in results:
        print(json.dumps(result, indent=2, ensure_ascii=False))
