import random
import re
import sys
import unicodedata
from abc import ABC, abstractmethod
from typing import Literal, Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

_UNABLE_TO_FETCH_CONTENT = "Unable to fetch content"
_UNABLE_TO_FETCH_TITLE = "Unable to fetch title"

if sys.version_info < (3, 9):
    HEADERS_DEFAULT = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        "Accept": "*/*",
    }
else:
    from fake_useragent import UserAgent

    HEADERS_DEFAULT = {"User-Agent": (UserAgent(platforms="mobile").random)}
TIMEOUT_DEFAULT = 10.0


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


HEADERS_LYNX = {
    "User-Agent": _get_lynx_useragent(),
    "Accept": "*/*",
}


class _WebSearchEntryGeneral(dict):
    def __init__(self, **data):
        super().__init__(**data)

    url: str
    title: str
    content: str


class WebSearchGeneral(ABC):
    @abstractmethod
    def search(
        self,
        query: str,
        number_results: int = 5,
        threshold: float = 0.2,
        timeout: Optional[float] = None,
    ) -> list:
        """Perform search and return results.
        Args:
            query (str): The search query.
            number_results (int, optional): The maximum number of results to return. Defaults to 5.
            threshold (float, optional): Minimum score threshold for results [0-1.0]. Defaults to 0.2.
            timeout (float, optional): Request timeout in seconds. Defaults to None.
        Returns:
            list: A list of search results.
        """
        pass

    @staticmethod
    def extract(url: str, timeout: Optional[float] = None) -> str:
        """Extract content from a given URL using available methods.

        Args:
            url (str): The URL to extract content from.
            timeout (float, optional): Request timeout in seconds. Defaults to TIMEOUT_DEFAULT (10). Usually not needed.

        Returns:
            str: Extracted content from the URL, or empty string if extraction fails.
        """
        # First try BeautifulSoup method
        content = WebSearchGeneral._get_content_with_bs4(
            url, timeout=timeout or TIMEOUT_DEFAULT
        )
        if not content:
            # Fallback to Jina Reader if BeautifulSoup fails
            content = WebSearchGeneral._get_content_with_jina_reader(
                url, timeout=timeout or TIMEOUT_DEFAULT
            )

        formatted_content = (
            WebSearchGeneral._format_text(content)
            if content
            else _UNABLE_TO_FETCH_CONTENT
        )
        return formatted_content

    @staticmethod
    def _fetch_webpage_content(entry: _WebSearchEntryGeneral) -> dict:
        """Retrieve complete webpage content from search result entry.

        Args:
            entry (_WebSearchEntryGeneral): The search result entry.

        Returns:
            Dict[str, str]: A dictionary containing the title, URL, content, and excerpt of the webpage.
        """
        url = entry["url"]
        if not url:
            raise ValueError("Result missing URL")

        try:
            content = WebSearchGeneral.extract(url)
        except Exception as e:
            content = _UNABLE_TO_FETCH_CONTENT
            logger.debug(f"Error retrieving webpage content: {e}")

        return {
            "title": entry.get("title", _UNABLE_TO_FETCH_TITLE),
            "url": url,
            "content": content,
            "excerpt": entry.get("content", _UNABLE_TO_FETCH_CONTENT),
        }

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
        text = WebSearchGeneral._remove_emojis(text)
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
