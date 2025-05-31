import re
import unicodedata
from typing import Literal, Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from .headers import HEADERS_DEFAULT, TIMEOUT_DEFAULT


class Fetch:
    """
    A class to handle fetching and extracting content from URLs.
    """

    @staticmethod
    def fetch_content(url: str, timeout: Optional[float] = None) -> str:
        """
        Fetch and extract content from a given URL.

        Args:
            url (str): The URL to fetch content from.
            timeout (float, optional): Request timeout in seconds. Defaults to None.

        Returns:
            str: Extracted content from the URL, or a message indicating failure if extraction fails.
        """
        try:
            content = _extract(url, timeout=timeout)
            return content
        except Exception as e:
            logger.error(f"Failed to fetch content from {url}: {e}")
            return "Unable to fetch content"


def _extract(url: str, timeout: Optional[float] = None) -> str:
    """
    Extract content from a given URL using available methods.

    Args:
        url (str): The URL to extract content from.
        timeout (float, optional): Request timeout in seconds. Defaults to TIMEOUT_DEFAULT (10). Usually not needed.

    Returns:
        str: Extracted content from the URL, or empty string if extraction fails.
    """
    # First try BeautifulSoup method
    content = _get_content_with_bs4(url, timeout=timeout or TIMEOUT_DEFAULT)
    if not content:
        # Fallback to Jina Reader if BeautifulSoup fails
        content = _get_content_with_jina_reader(url, timeout=timeout or TIMEOUT_DEFAULT)

    formatted_content = _format_text(content) if content else "Unable to fetch content"
    return formatted_content


def _get_content_with_jina_reader(
    url: str,
    return_format: Literal["markdown", "text", "html"] = "text",
    timeout: Optional[float] = None,
) -> str:
    """
    Fetch parsed content from Jina AI for a given URL.

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


def _get_content_with_bs4(
    url: str,
    timeout: Optional[float] = None,
) -> str:
    """
    Utilizes BeautifulSoup to fetch and parse the content of a webpage.

    Args:
        url (str): The URL of the webpage.
        timeout (Optional[float]): Timeout for the HTTP request. Defaults to TIMEOUT_DEFAULT.

    Returns:
        str: Parsed text content of the webpage.
    """
    try:
        response = httpx.get(
            url,
            headers=HEADERS_DEFAULT,
            timeout=timeout or TIMEOUT_DEFAULT,
            follow_redirects=True,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
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


def _format_text(text: str) -> str:
    """
    Format text content.

    Args:
        text (str): The input text.

    Returns:
        str: Formatted text.
    """
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    text = text.strip()
    text = _remove_emojis(text)
    return text


def _remove_emojis(text: str) -> str:
    """
    Remove emoji expressions from text.

    Args:
        text (str): The input text.

    Returns:
        str: Text with emojis removed.
    """
    return "".join(c for c in text if not unicodedata.category(c).startswith("So"))
