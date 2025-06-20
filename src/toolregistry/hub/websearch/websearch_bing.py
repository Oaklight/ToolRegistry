import base64
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from time import sleep
from typing import Dict, Generator, List, Optional, Set
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup, Tag
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

    @staticmethod
    def _extract_real_url(bing_url: str) -> str:
        """Extract the real URL from Bing's redirect URL.

        Args:
            bing_url: The Bing redirect URL

        Returns:
            The actual destination URL, or the original URL if extraction fails
        """
        try:
            # Parse the URL
            parsed = urlparse(bing_url)

            # Check if it's a Bing redirect URL
            if "bing.com" not in parsed.netloc or "/ck/a" not in parsed.path:
                return bing_url

            # Extract query parameters
            query_params = parse_qs(parsed.query)

            # Look for the 'u' parameter which contains the base64 encoded URL
            if "u" in query_params:
                encoded_url = query_params["u"][0]
                try:
                    # The URL is base64 encoded with some prefix, try to decode
                    if encoded_url.startswith("a1"):
                        # Remove the 'a1' prefix and decode
                        encoded_part = encoded_url[2:]
                        # Add padding if needed for base64 decoding
                        padding = 4 - (len(encoded_part) % 4)
                        if padding != 4:
                            encoded_part += "=" * padding
                        decoded_bytes = base64.b64decode(encoded_part)
                        decoded_url = decoded_bytes.decode("utf-8")
                        return decoded_url
                except Exception as e:
                    logger.debug(f"Failed to decode base64 URL: {e}")
                    pass

            # If base64 decoding fails, try URL unquoting
            if "u" in query_params:
                try:
                    return unquote(query_params["u"][0])
                except Exception as e:
                    logger.debug(f"Failed to unquote URL: {e}")
                    pass

            # If all else fails, return the original URL
            return bing_url

        except Exception as e:
            logger.debug(f"Error extracting real URL from {bing_url}: {e}")
            return bing_url

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
                        partial(
                            self._fetch_webpage_content,
                            timeout=timeout or TIMEOUT_DEFAULT,
                            proxy=self.proxy,
                        ),
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
            timeout=timeout or TIMEOUT_DEFAULT,
            follow_redirects=True,
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
            if not isinstance(result, Tag):
                continue

            link_tag = result.find("a", href=True)
            # Skip non-Tag elements
            if not link_tag or not isinstance(link_tag, Tag):
                continue

            h2_tag = result.find("h2")
            if not isinstance(h2_tag, Tag):
                continue

            link_tag = h2_tag.find("a")
            if not isinstance(link_tag, Tag):
                continue

            caption = result.find("div", class_="b_caption")
            if not isinstance(caption, Tag):
                continue

            description_tag = caption.find("p")
            if not isinstance(description_tag, Tag):
                continue

            if not (link_tag and h2_tag and description_tag):
                continue

            try:
                raw_link = link_tag.get("href")
                if not raw_link or not isinstance(raw_link, str):
                    continue

                # Extract the real URL from Bing's redirect URL
                link = WebSearchBing._extract_real_url(raw_link)

                if link in fetched_links:
                    continue

                fetched_links.add(link)
                title = h2_tag.get_text() if h2_tag else ""
                description = description_tag.get_text() if description_tag else ""
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
