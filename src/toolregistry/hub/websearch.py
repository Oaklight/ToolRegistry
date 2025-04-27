import re
import unicodedata
from abc import ABC, abstractmethod
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


class WebSearchGeneral(ABC):
    @abstractmethod
    def extract(self, url: str) -> str:
        """Extract content from a URL.
        Args:
            url (str): The URL to extract content from.
        Returns:
            str: The extracted content.
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        number_of_results: int = 5,
        threshold: float = 0.2,
        timeout: float = None,
    ) -> list:
        """Perform search and return results.
        Args:
            query (str): The search query.
            number_of_results (int, optional): The maximum number of results to return. Defaults to 5.
            threshold (float, optional): Minimum score threshold for results [0-1.0]. Defaults to 0.2.
            timeout (float, optional): Request timeout in seconds. Defaults to None.
        Returns:
            list: A list of search results.
        """
        pass

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
