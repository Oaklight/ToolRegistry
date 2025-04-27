"""googlesearch is a Python library for searching Google, easily."""

import random
from time import sleep
from typing import Dict, List
from urllib.parse import unquote  # to decode the url

import httpx
from bs4 import BeautifulSoup


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


class SearchResult(dict):
    # def __init__(self, url, title, description):
    #     self.url = url
    #     self.title = title
    #     self.description = description

    # def __repr__(self):
    #     return f"SearchResult(url={self.url}, title={self.title}, description={self.description})"
    def __init__(self, **data):
        super().__init__(**data)

    url: str
    title: str
    description: str


def _parse_google_entries(html, fetched_links, num_results):
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

        yield {"link": link, "title": title, "description": description}


def _meta_google_search(
    query,
    num_results=10,
    proxy=None,
    sleep_interval=0,
    timeout=5,
    region=None,
    start_num=0,
) -> List[Dict[str, str]]:
    """Search the Google search engine"""
    proxies = (
        {"https": proxy, "http": proxy}
        if proxy and (proxy.startswith("https") or proxy.startswith("http"))
        else None
    )
    results = []
    fetched_results = 0
    fetched_links = set()

    # Create a persistent client with connection pooling
    with httpx.Client(
        proxy=proxies,
        # verify=ssl_verify,
        headers={
            "User-Agent": _get_lynx_useragent(),
            "Accept": "*/*",
        },
        timeout=timeout,
    ) as client:
        start = start_num
        while fetched_results < num_results:
            response = client.get(
                url="https://www.google.com/search",
                params={
                    "q": query,
                    "num": num_results - start + 2,
                    # "hl": "lang",
                    "start": start,
                    # "safe": "active",
                    "gl": region,
                },
                cookies={
                    "CONSENT": "PENDING+987",
                    "SOCS": "CAESHAgBEhIaAB",
                },
            )
            response.raise_for_status()

            batch_entries = list(
                _parse_google_entries(
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


if __name__ == "__main__":
    # Example usage of the function
    for result in _meta_google_search("巴塞罗那今日天气"):
        print(result)
