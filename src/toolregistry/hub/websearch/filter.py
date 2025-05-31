import os
import time
from typing import Dict, List, Optional

import httpx
from loguru import logger

# Cache file path for the blocklist
BLOCKLIST_CACHE_PATH = os.path.expanduser(
    "~/.cache/toolregistry/websearch_blocklist.txt"
)
# Cache duration in seconds (e.g., 30 days)
CACHE_DURATION = 24 * 60 * 60 * 30
UBLOCKLIST_URL = "https://raw.githubusercontent.com/eallion/uBlacklist-subscription-compilation/main/uBlacklist.txt"
GITHUB_RAW_PROXY = "https://rawgithubusercontent.deno.dev"
# Module-level variable to store blocked items
_blocked_items: set[str] = set()
_last_blocklist_content = None
_last_blocklist_timestamp = None


def parse_blocklist_content(content: str) -> None:
    """Parse blocklist content into the module-level _blocked_items set.

    Args:
        content (str): The blocklist content to parse.
    """
    global _blocked_items
    _blocked_items.clear()
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("!"):
            # Handle uBlacklist format or simple domain/URL list
            if line.startswith("*://"):
                # Format like "*://*.example.com/*" or "*://example.com/*"
                try:
                    # Remove "*://" prefix
                    domain_part = line[5:]
                    # Handle "*.example.com" or "example.com"
                    if domain_part.startswith("*."):
                        domain_part = domain_part[2:]
                    # Remove trailing "/*" or similar patterns
                    if domain_part.endswith("/*"):
                        domain_part = domain_part[:-1]
                    # Add the cleaned domain part
                    if domain_part:
                        _blocked_items.add(domain_part)
                except IndexError:
                    continue
            else:
                # Simple domain or URL
                _blocked_items.add(line)
    logger.debug("Parsed blocklist with {} entries", len(_blocked_items))


def fetch_and_cache_blocklist(
    url: str,
    cache_path: str = BLOCKLIST_CACHE_PATH,
    cache_duration: int = CACHE_DURATION,
) -> Optional[str]:
    """Fetch the blocklist from the specified URL and cache it locally.

    Args:
        url (str): The URL of the blocklist to fetch.
        cache_path (str, optional): Path to store the cached blocklist. Defaults to BLOCKLIST_CACHE_PATH.
        cache_duration (int, optional): Duration in seconds to keep the cache before refreshing. Defaults to CACHE_DURATION.

    Returns:
        Optional[str]: The content of the blocklist if successful, None otherwise.
    """
    global _last_blocklist_timestamp, _last_blocklist_content

    # Ensure cache directory exists
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    # Check if cache exists and is still valid
    if os.path.exists(cache_path):
        cache_age = time.time() - os.path.getmtime(cache_path)
        if cache_age < cache_duration and _last_blocklist_timestamp:
            logger.debug("Using cached blocklist from module-level cache")
            return _last_blocklist_content

    # Fetch the blocklist from the URL
    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(url)
            response.raise_for_status()
            content = response.text

            # Save to cache
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.debug("Fetched and cached blocklist to {}", cache_path)

            # Update module-level cache
            _last_blocklist_content = content
            _last_blocklist_timestamp = time.time()

            parse_blocklist_content(content)
            return content
    except httpx.TimeoutException as e:
        logger.error("Timeout when fetching blocklist from {}: {}", url, e)
        if url.startswith("https://raw.githubusercontent.com"):
            return _try_fetch_from_proxy(url, cache_path)
        return _fallback_to_cache(cache_path)
    except Exception as e:
        logger.error("Failed to fetch blocklist from {}: {}", url, e)
        return _fallback_to_cache(cache_path)


def _try_fetch_from_proxy(url: str, cache_path: str) -> Optional[str]:
    """Attempt to fetch the blocklist from a proxy URL if the original times out.

    Args:
        url (str): The original URL to transform into a proxy URL.
        cache_path (str): Path to store the cached blocklist.

    Returns:
        Optional[str]: The content of the blocklist if successful, None otherwise.
    """
    proxy_url = url.replace("https://raw.githubusercontent.com", GITHUB_RAW_PROXY)
    logger.debug("Attempting to fetch blocklist from proxy: {}", proxy_url)
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(proxy_url)
            response.raise_for_status()
            content = response.text

            # Save to cache
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.debug("Fetched and cached blocklist from proxy to {}", cache_path)
            parse_blocklist_content(content)
            return content
    except Exception as e:
        logger.error("Failed to fetch blocklist from proxy {}: {}", proxy_url, e)
        return _fallback_to_cache(cache_path)


def _fallback_to_cache(cache_path: str) -> Optional[str]:
    """Fallback to cached content if available, even if outdated.

    Args:
        cache_path (str): Path to the cached blocklist.

    Returns:
        Optional[str]: The content of the cached blocklist if available, None otherwise.
    """
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                logger.debug(
                    "Falling back to outdated cached blocklist from {}", cache_path
                )
                content = f.read()
                parse_blocklist_content(content)
                return content
        except Exception as e:
            logger.error("Error reading fallback cached blocklist: {}", e)
    return None


def filter_search_results(
    results: List[Dict[str, str]], blocklist_content: Optional[str] = None
) -> List[Dict[str, str]]:
    """Filter search results based on a blocklist.

    Args:
        results (List[Dict[str, str]]): List of search results to filter.
        blocklist_content (Optional[str], optional): Content of the blocklist. If None, it will be fetched from UBLOCKLIST_URL env variable. Defaults to None.

    Returns:
        List[Dict[str, str]]: Filtered list of search results.
    """
    global _last_blocklist_content
    if blocklist_content is None:
        url = UBLOCKLIST_URL
        blocklist_content = fetch_and_cache_blocklist(url)
        if blocklist_content is None:
            logger.error(
                "Failed to obtain blocklist content from {}, skipping filtering", url
            )
            return results
    elif blocklist_content != _last_blocklist_content:
        parse_blocklist_content(blocklist_content)
        _last_blocklist_content = blocklist_content
        logger.debug("Updated blocked items with new content")

    if not _blocked_items:
        logger.debug("Blocklist is empty or contains no valid entries")
        return results

    filtered_results = []
    for result in results:
        url = result.get("url", "")
        if not url:
            continue

        # Check if the URL or its domain is in the blocklist
        blocked = False
        for blocked_item in _blocked_items:
            if blocked_item in url:
                blocked = True
                break

        if not blocked:
            filtered_results.append(result)
        else:
            logger.debug("Filtered out URL: {}", url)

    logger.debug("Filtered from {} to {} results", len(results), len(filtered_results))
    return filtered_results
