import re


def normalize_tool_name(name: str) -> str:
    """Normalize tool name to snake_case format and remove dots and spaces.
    Also handles OpenAPI-style duplicate names like 'add_add_get' by converting to 'add_get'.

    Args:
        name: Original tool name in various formats (including CamelCase, UpperCamelCase, or containing spaces)

    Returns:
        str: Normalized name in snake_case without dots or spaces
    """
    # First check for OpenAPI-style duplicate names (e.g. "add_add_get")
    openapi_pattern = r"^([a-zA-Z0-9]+)_\1_([a-zA-Z0-9]+)$"
    match = re.match(openapi_pattern, name)
    if match:
        return f"{match.group(1)}_{match.group(2)}"

    # Replace all special chars (., -, @, etc.) with single underscore
    name = re.sub(r"[.\-@]+", "_", name)

    # Remove spaces and collapse multiple spaces into a single space
    name = re.sub(r"\s+", " ", name).strip()

    # Replace spaces with underscores
    name = name.replace(" ", "_")

    # Convert CamelCase and UpperCamelCase to snake_case
    # Handles all cases including:
    # XMLParser -> xml_parser
    # getUserIDFromDB -> get_user_id_from_db
    # HTTPRequest -> http_request
    name = re.sub(r"(?<!^)(?=[A-Z][a-z])|(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()

    # Collapse multiple underscores into single underscore
    return re.sub(r"_+", "_", name)
