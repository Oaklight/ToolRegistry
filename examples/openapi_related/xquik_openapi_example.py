"""Register Xquik's public OpenAPI spec as ToolRegistry tools.

Set ``XQUIK_API_KEY`` to enable authenticated calls. The script lists the
registered tools by default. Set ``XQUIK_RUN_EXAMPLE=1`` to run a small
``search_tweets`` example with your own API key.
"""

import os
from pprint import pprint

from toolregistry import ToolRegistry
from toolregistry.integrations.openapi import HttpClientConfig, load_openapi_spec

XQUIK_BASE_URL = "https://xquik.com"
XQUIK_OPENAPI_SPEC_URL = f"{XQUIK_BASE_URL}/openapi.json"


def build_xquik_registry() -> ToolRegistry:
    """Build a ToolRegistry from the Xquik OpenAPI document."""
    api_key = os.getenv("XQUIK_API_KEY")
    headers = {"x-api-key": api_key} if api_key else None

    client_config = HttpClientConfig(
        base_url=XQUIK_BASE_URL,
        headers=headers,
        timeout=15.0,
    )
    openapi_spec = load_openapi_spec(XQUIK_OPENAPI_SPEC_URL)

    registry = ToolRegistry()
    registry.register_from_openapi(client_config, openapi_spec, namespace="xquik")
    return registry


def main() -> None:
    """List registered Xquik tools, then optionally run a live query."""
    registry = build_xquik_registry()
    tools = registry.list_tools()

    print(f"Registered {len(tools)} Xquik OpenAPI tools.")
    pprint([name for name in tools if name.startswith("xquik-search")])

    if os.getenv("XQUIK_RUN_EXAMPLE") != "1":
        return

    if not os.getenv("XQUIK_API_KEY"):
        raise RuntimeError("Set XQUIK_API_KEY before setting XQUIK_RUN_EXAMPLE=1")

    search_tweets = registry.get_callable("xquik-search_tweets")
    query = os.getenv("XQUIK_QUERY", "from:xquik")
    pprint(search_tweets(q=query, queryType="Latest", limit=5))


if __name__ == "__main__":
    main()
