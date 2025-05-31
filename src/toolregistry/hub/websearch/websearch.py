from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger

from .fetch import Fetch

_UNABLE_TO_FETCH_CONTENT = "Unable to fetch content"
_UNABLE_TO_FETCH_TITLE = "Unable to fetch title"


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
            content = Fetch.fetch_content(url)
        except Exception as e:
            content = _UNABLE_TO_FETCH_CONTENT
            logger.debug(f"Error retrieving webpage content: {e}")

        return {
            "title": entry.get("title", _UNABLE_TO_FETCH_TITLE),
            "url": url,
            "content": content,
            "excerpt": entry.get("content", _UNABLE_TO_FETCH_CONTENT),
        }
