import time
from concurrent.futures import ProcessPoolExecutor
from time import sleep
from typing import Dict, Generator, List, Optional, Set
from urllib.parse import unquote  # to decode the url

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from .filter import filter_search_results
from .headers import HEADERS_LYNX, TIMEOUT_DEFAULT
from .websearch import WebSearchGeneral


class _WebSearchEntryGoogle(dict):
    """Internal class for representing Google search results"""

    def __init__(self, **data):
        super().__init__(**data)

    url: str
    title: str
    content: str


class WebSearchGoogle(WebSearchGeneral):
    """WebSearchGoogle provides a unified interface for performing web searches on Google.
    It handles search queries and result processing.

    Features:
    - Performs web searches using Google
    - Returns formatted results with title, URL and description
    - Supports proxy and region settings

    Examples:
        >>> from toolregistry.hub.websearch_google import WebSearchGoogle
        >>> searcher = WebSearchGoogle()
        >>> results = searcher.search("python web scraping", number_results=3)
        >>> for result in results:
        ...     print(result["title"])
    """

    def __init__(
        self,
        google_base_url: str = "https://www.google.com",
        proxy: Optional[str] = None,
    ):
        """Initialize WebSearchGoogle with configuration parameters.

        Args:
            google_base_url (str): Base URL for the Google search. Defaults to "https://www.google.com".
            proxy: Optional proxy server URL (e.g. "http://proxy.example.com:8080")
        """
        self.google_base_url = google_base_url.rstrip("/")
        if not self.google_base_url.endswith("/search"):
            self.google_base_url += "/search"  # Ensure the URL ends with /search

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
                - 'content': The description/content from Google
                - 'excerpt': Same as content (for compatibility with WebSearchSearXNG)
        """
        try:
            results = WebSearchGoogle._meta_search_google(
                query,
                num_results=number_results * 2,
                proxy=self.proxy,
                timeout=timeout or TIMEOUT_DEFAULT,
                google_base_url=self.google_base_url,
            )

            # TODO: find out how to get score from results
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
    def _meta_search_google(
        query,
        num_results=10,
        proxy: Optional[str] = None,
        sleep_interval: float = 0,
        timeout: float = 5,
        start_num: int = 0,
        google_base_url: str = "https://www.google.com/search",
    ) -> List[_WebSearchEntryGoogle]:
        """Search the Google search engine"""
        results = []
        fetched_results = 0
        fetched_links: Set[str] = set()

        # Create a persistent client with connection pooling
        with httpx.Client(
            proxy=proxy,
            headers=HEADERS_LYNX,
            timeout=timeout,
        ) as client:
            start = start_num
            while fetched_results < num_results:
                response = client.get(
                    url=google_base_url,
                    params={
                        "q": query,
                        "num": num_results - start + 2,
                        "start": start,
                    },
                    cookies={
                        "CONSENT": "PENDING+987",
                        "SOCS": "CAESHAgBEhIaAB",
                    },
                )
                response.raise_for_status()

                batch_entries = list(
                    WebSearchGoogle._parse_google_entries(
                        response.text, fetched_links, num_results - fetched_results
                    )
                )
                if len(batch_entries) == 0:
                    break

                fetched_results += len(batch_entries)
                results.extend(batch_entries)

                start += 10
                sleep(sleep_interval)

        return results

    @staticmethod
    def _parse_google_entries(
        html: str, fetched_links: Set[str], num_results: int
    ) -> Generator[_WebSearchEntryGoogle, None, None]:
        """Parse HTML content from Google search results."""
        soup = BeautifulSoup(html, "html.parser")
        result_block = soup.find_all("div", class_="ezO2md")
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

            title_tag = link_tag.find("span", class_="CVA68e")
            description_tag = result.find("span", class_="FrIlee")

            if not (link_tag and title_tag and description_tag):
                continue

            try:
                link = unquote(link_tag["href"].split("&")[0].replace("/url?q=", ""))
                if link in fetched_links:
                    continue

                fetched_links.add(link)
                title = title_tag.text if title_tag else ""
                description = description_tag.text if description_tag else ""
                new_results += 1

                yield _WebSearchEntryGoogle(
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
    searcher = WebSearchGoogle()
    results = searcher.search("巴塞罗那今日天气", 5)
    for result in results:
        print(json.dumps(result, indent=2, ensure_ascii=False))
