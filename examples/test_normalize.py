from toolregistry.utils import normalize_tool_name


def test_normalize():
    # Test OpenAPI-style duplicate names
    assert normalize_tool_name("add_add_get") == "add_get"
    assert normalize_tool_name("subtract_subtract_get") == "subtract_get"
    assert normalize_tool_name("multiply_multiply_post") == "multiply_post"

    # Test with different HTTP methods
    assert normalize_tool_name("user_user_patch") == "user_patch"
    assert normalize_tool_name("item_item_delete") == "item_delete"

    # Test regular names
    assert normalize_tool_name("calculateTotal") == "calculate_total"
    assert normalize_tool_name("getUserInfo") == "get_user_info"
    assert normalize_tool_name("ProcessData") == "process_data"

    # Test with spaces and special chars
    assert normalize_tool_name("get user info") == "get_user_info"
    assert normalize_tool_name("process.data") == "process_data"
    assert normalize_tool_name("parse-json") == "parse_json"
    assert normalize_tool_name("encode@url") == "encode_url"

    # Test with numbers
    assert normalize_tool_name("getUser2Info") == "get_user2_info"
    assert normalize_tool_name("process2.data") == "process2_data"

    # Test with consecutive special chars
    assert normalize_tool_name("parse..json") == "parse_json"
    assert normalize_tool_name("encode--url") == "encode_url"
    assert normalize_tool_name("user__info") == "user_info"

    # Test edge cases
    assert normalize_tool_name("") == ""
    assert normalize_tool_name("A") == "a"
    assert normalize_tool_name("_") == "_"
    assert normalize_tool_name(".") == "_"
    assert normalize_tool_name(" ") == ""

    # Additional test cases for more complex scenarios
    assert normalize_tool_name("XMLParser") == "xml_parser"
    assert normalize_tool_name("parse@JSON.data") == "parse_json_data"
    assert normalize_tool_name("getUserIDFromDB") == "get_user_id_from_db"
    assert normalize_tool_name("HTTPRequest") == "http_request"
    assert normalize_tool_name("process XML and JSON") == "process_xml_and_json"
    assert normalize_tool_name("OpenAPI service") == "open_api_service"

    print("All 26 test cases passed!")


if __name__ == "__main__":
    test_normalize()
