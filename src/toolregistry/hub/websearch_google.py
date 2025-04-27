"""googlesearch is a Python library for searching Google, easily."""

import random
from time import sleep
from typing import Dict, List, Optional
from urllib.parse import unquote  # to decode the url

import httpx
from bs4 import BeautifulSoup
from loguru import logger


def _get_lynx_useragent():
    """
    Generates a random user agent string mimicking the format of various software versions.

    The user agent string is composed of:
    - Lynx version: Lynx/x.y.z where x is 2-3, y is 8-9, and z is 0-2
    - libwww version: libwww-FM/x.y where x is 2-3 and y is 13-15
    - SSL-MM version: SSL-MM/x.y where x is 1-2 and y is 3-5
    - OpenSSL version: OpenSSL/x.y.z where x is 1-3, y is 0-4, and z is 0-9

    Returns:
        str: A randomly generated user agent string.
    """
    lynx_version = (
        f"Lynx/{random.randint(2, 3)}.{random.randint(8, 9)}.{random.randint(0, 2)}"
    )
    libwww_version = f"libwww-FM/{random.randint(2, 3)}.{random.randint(13, 15)}"
    ssl_mm_version = f"SSL-MM/{random.randint(1, 2)}.{random.randint(3, 5)}"
    openssl_version = (
        f"OpenSSL/{random.randint(1, 3)}.{random.randint(0, 4)}.{random.randint(0, 9)}"
    )
    return f"{lynx_version} {libwww_version} {ssl_mm_version} {openssl_version}"


class WebSearchGoogle:
    """WebSearchGoogle provides a unified interface for performing web searches on Google.
    It handles search queries and result processing.

    Features:
    - Performs web searches using Google
    - Returns formatted results with title, URL and description
    - Supports proxy and region settings

    Examples:
        >>> from toolregistry.hub.websearch_google import WebSearchGoogle
        >>> searcher = WebSearchGoogle()
        >>> results = searcher.search("python web scraping", number_of_results=3)
        >>> for result in results:
        ...     print(result["title"])
    """

    @staticmethod
    def _parse_google_entries(html: str, fetched_links: set, num_results: int):
        """Parse HTML content from Google search results."""
        soup = BeautifulSoup(html, "html.parser")
        result_block = soup.find_all("div", class_="ezO2md")
        new_results = 0

        for result in result_block:
            if new_results >= num_results:
                break

            link_tag = result.find("a", href=True)
            title_tag = link_tag.find("span", class_="CVA68e") if link_tag else None
            description_tag = result.find("span", class_="FrIlee")

            if not (link_tag and title_tag and description_tag):
                continue

            link = unquote(link_tag["href"].split("&")[0].replace("/url?q=", ""))
            if link in fetched_links:
                continue

            fetched_links.add(link)
            title = title_tag.text if title_tag else ""
            description = description_tag.text if description_tag else ""
            new_results += 1

            yield {
                "title": title,
                "url": link,
                "content": description,
                "excerpt": description,
            }

    def __init__(
        self,
        google_base_url: str = "https://www.google.com",
        proxy: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """Initialize WebSearchGoogle with configuration parameters.

        Args:
            proxy: Optional proxy server URL (e.g. "http://proxy.example.com:8080")
            region: Optional region code for localized results (e.g. "us" for United States)
            timeout: Request timeout in seconds. Default is 5.0.
        """
        self.google_base_url = google_base_url.rstrip("/")
        if not self.google_base_url.endswith("/search"):
            self.google_base_url += "/search"  # Ensure the URL ends with /search

        self.proxy = proxy
        self.timeout = timeout

    def search(
        self,
        query: str,
        number_of_results: int = 5,
        timeout: Optional[float] = None,
    ) -> List[Dict[str, str]]:
        """Perform search and return results.

        Args:
            query: The search query.
            number_of_results: The maximum number of results to return. Default is 5.
            timeout: Optional timeout override in seconds.

        Returns:
            List of search results, each containing:
            - 'title': The title of the search result
            - 'url': The URL of the search result
            - 'content': The description/content from Google
            - 'excerpt': Same as content (for compatibility with WebSearchSearxng)
        """
        proxies = (
            {"https": self.proxy, "http": self.proxy}
            if self.proxy
            and (self.proxy.startswith("https") or self.proxy.startswith("http"))
            else None
        )
        results = []
        fetched_results = 0
        fetched_links = set()
        timeout = timeout or self.timeout

        # Create a persistent client with connection pooling
        with httpx.Client(
            proxy=proxies,
            headers={
                "User-Agent": _get_lynx_useragent(),
                "Accept": "*/*",
            },
            timeout=timeout,
        ) as client:
            start = 0
            while fetched_results < number_of_results:
                try:
                    response = client.get(
                        url=self.google_base_url,
                        params={
                            "q": query,
                            "num": number_of_results - start + 2,
                            "start": start,
                            # "gl": self.region,
                        },
                        cookies={
                            "CONSENT": "PENDING+987",
                            "SOCS": "CAESHAgBEhIaAB",
                        },
                    )
                    response.raise_for_status()

                    batch_entries = list(
                        WebSearchGoogle._parse_google_entries(
                            response.text,
                            fetched_links,
                            number_of_results - fetched_results,
                        )
                    )
                    if len(batch_entries) == 0:
                        break

                    fetched_results += len(batch_entries)
                    results.extend(batch_entries)

                    start += 10
                    sleep(0.5)  # Be polite with delay between requests

                except httpx.RequestError as e:
                    logger.debug(f"Request error: {e}")
                    break
                except httpx.HTTPStatusError as e:
                    logger.debug(f"HTTP error: {e.response.status_code}")
                    break

        return results[:number_of_results]


if __name__ == "__main__":
    # Example usage
    searcher = WebSearchGoogle()
    results = searcher.search("巴塞罗那今日天气", number_of_results=3)
    for result in results:
        print(f"Title: {result['title']}")
        print(f"URL: {result['url']}")
        print(f"Content: {result['content']}\n")
