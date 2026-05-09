"""Unit tests for the utils module."""

from toolregistry._vendor.httpclient import AsyncClient, Client
from toolregistry.utils import HttpClientConfig, HttpxClientConfig, normalize_tool_name


class TestHttpClientConfig:
    """Test cases for the HttpClientConfig class."""

    def test_initialization_with_minimal_params(self):
        """Test HttpClientConfig initialization with minimal parameters."""
        config = HttpClientConfig(base_url="https://api.example.com")

        assert config.base_url == "https://api.example.com"
        assert config.headers == {}
        assert config.timeout == 10.0
        assert config.auth is None
        assert config.extra_options == {}

    def test_initialization_with_all_params(self):
        """Test HttpClientConfig initialization with all parameters."""
        headers = {"Authorization": "Bearer token"}
        auth = ("username", "password")
        extra_options = {"verify": False, "max_redirects": 10}

        config = HttpClientConfig(
            base_url="https://api.example.com/",
            headers=headers,
            timeout=30.0,
            auth=auth,
            **extra_options,
        )

        assert config.base_url == "https://api.example.com"  # Trailing slash removed
        assert config.headers == headers
        assert config.timeout == 30.0
        assert config.auth == auth
        assert config.extra_options == extra_options

    def test_base_url_trailing_slash_removal(self):
        """Test that trailing slash is removed from base_url."""
        config = HttpClientConfig(base_url="https://api.example.com/")

        assert config.base_url == "https://api.example.com"

    def test_base_url_multiple_trailing_slashes(self):
        """Test that multiple trailing slashes are removed."""
        config = HttpClientConfig(base_url="https://api.example.com///")

        assert config.base_url == "https://api.example.com"

    def test_headers_default_to_empty_dict(self):
        """Test that headers default to empty dict when None."""
        config = HttpClientConfig(base_url="https://api.example.com", headers=None)

        assert config.headers == {}

    def test_to_client_sync(self):
        """Test creating synchronous client."""
        config = HttpClientConfig(
            base_url="https://api.example.com",
            headers={"Content-Type": "application/json"},
            timeout=20.0,
            auth=("user", "pass"),
            verify=False,
        )

        client = config.to_client(use_async=False)

        assert hasattr(client, "get")
        assert hasattr(client, "request")
        assert hasattr(client, "close")
        assert isinstance(client._client, Client)

    def test_to_client_async(self):
        """Test creating asynchronous client."""
        config = HttpClientConfig(
            base_url="https://api.example.com",
            headers={"Content-Type": "application/json"},
            timeout=20.0,
            auth=("user", "pass"),
            verify=False,
        )

        client = config.to_client(use_async=True)

        assert hasattr(client, "get")
        assert hasattr(client, "request")
        assert hasattr(client, "aclose")
        assert isinstance(client._client, AsyncClient)

    def test_to_client_default_sync(self):
        """Test that to_client defaults to synchronous client."""
        config = HttpClientConfig(base_url="https://api.example.com")

        client = config.to_client()

        assert isinstance(client._client, Client)

    def test_to_client_with_extra_options(self):
        """Test creating client with extra options."""
        config = HttpClientConfig(
            base_url="https://api.example.com",
            verify=False,
            max_redirects=10,
        )

        client = config.to_client()

        assert client is not None  # Client should be created successfully

    def test_base_url_prepended_to_relative_path(self):
        """Test that base_url is prepended to relative paths."""
        config = HttpClientConfig(base_url="https://api.example.com")
        client = config.to_client(use_async=False)

        assert client._url("/api/test") == "https://api.example.com/api/test"

    def test_absolute_url_not_modified(self):
        """Test that absolute URLs are passed through unchanged."""
        config = HttpClientConfig(base_url="https://api.example.com")
        client = config.to_client(use_async=False)

        assert client._url("https://other.com/test") == "https://other.com/test"

    def test_deprecated_alias(self):
        """Test that HttpxClientConfig emits deprecation warning."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = HttpxClientConfig(base_url="https://api.example.com")
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "HttpxClientConfig" in str(w[0].message)
            assert isinstance(config, HttpClientConfig)


class TestHttpClientConfigPersistentExtended:
    """Additional tests for persistent client methods (supplements test_persistent_connection.py)."""

    def test_persistent_client_initial_state(self):
        """Test that persistent clients are initially None."""
        config = HttpClientConfig(base_url="https://api.example.com")

        assert config._sync_client is None
        assert config._async_client is None

    def test_to_client_creates_fresh_instances(self):
        """Test that to_client always creates fresh (non-persistent) instances."""
        config = HttpClientConfig(base_url="https://api.example.com")
        client1 = config.to_client(use_async=False)
        client2 = config.to_client(use_async=False)

        assert client1 is not client2
        client1.close()
        client2.close()


class TestNormalizeToolName:
    """Test cases for the normalize_tool_name function."""

    def test_normalize_simple_name(self):
        """Test normalizing a simple name."""
        result = normalize_tool_name("simple_name")

        assert result == "simple_name"

    def test_normalize_camel_case(self):
        """Test normalizing CamelCase names."""
        test_cases = [
            ("CamelCase", "camel_case"),
            ("XMLParser", "xml_parser"),
            ("HTTPRequest", "http_request"),
            ("getUserID", "get_user_id"),
            ("parseXMLData", "parse_xml_data"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected, (
                f"Failed for {input_name}: got {result}, expected {expected}"
            )

    def test_normalize_upper_camel_case(self):
        """Test normalizing UpperCamelCase names."""
        test_cases = [
            ("UpperCamelCase", "upper_camel_case"),
            ("MyClassName", "my_class_name"),
            ("APIEndpoint", "api_endpoint"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_with_dots(self):
        """Test normalizing names with dots."""
        test_cases = [
            ("name.with.dots", "name_with_dots"),
            ("module.function", "module_function"),
            ("a.b.c.d", "a_b_c_d"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_with_dashes(self):
        """Test normalizing names with dashes."""
        test_cases = [
            ("name-with-dashes", "name_with_dashes"),
            ("kebab-case-name", "kebab_case_name"),
            ("multi---dash", "multi_dash"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_with_at_symbols(self):
        """Test normalizing names with @ symbols."""
        test_cases = [
            ("name@with@at", "name_with_at"),
            ("@decorator", "_decorator"),
            ("email@domain", "email_domain"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_with_spaces(self):
        """Test normalizing names with spaces."""
        test_cases = [
            ("name with spaces", "name_with_spaces"),
            ("  multiple   spaces  ", "multiple_spaces"),
            ("single space", "single_space"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_openapi_duplicate_pattern(self):
        """Test normalizing OpenAPI-style duplicate names."""
        test_cases = [
            ("add_add_get", "add_get"),
            ("user_user_post", "user_post"),
            ("data_data_delete", "data_delete"),
            ("item_item_put", "item_put"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_openapi_non_duplicate_pattern(self):
        """Test that non-duplicate patterns are not affected."""
        test_cases = [
            ("add_user_get", "add_user_get"),
            ("user_data_post", "user_data_post"),
            ("get_add_item", "get_add_item"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_mixed_special_characters(self):
        """Test normalizing names with mixed special characters."""
        test_cases = [
            ("name.with-mixed@chars", "name_with_mixed_chars"),
            ("complex.name-with@multiple.types", "complex_name_with_multiple_types"),
            ("a.b-c@d.e-f", "a_b_c_d_e_f"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_multiple_underscores_collapsed(self):
        """Test that multiple underscores are collapsed to single underscore."""
        test_cases = [
            ("name__with__double", "name_with_double"),
            ("name___with___triple", "name_with_triple"),
            ("name____many____underscores", "name_many_underscores"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_complex_camel_case_with_numbers(self):
        """Test normalizing complex CamelCase with numbers."""
        test_cases = [
            ("getUserIDFromDB", "get_user_id_from_db"),
            ("parseXML2JSON", "parse_xml2_json"),
            ("HTTP2Request", "http2_request"),
            ("base64Encode", "base64_encode"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_edge_cases(self):
        """Test normalizing edge cases."""
        test_cases = [
            ("", ""),
            ("a", "a"),
            ("A", "a"),
            ("_", "_"),
            ("__", "_"),
            ("123", "123"),
            ("_123", "_123"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_preserves_numbers(self):
        """Test that numbers are preserved in normalization."""
        test_cases = [
            ("function123", "function123"),
            ("get2Items", "get2_items"),
            ("parse3DData", "parse3_d_data"),
            ("version2API", "version2_api"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_consecutive_capitals(self):
        """Test normalizing consecutive capital letters."""
        test_cases = [
            ("XMLHTTPRequest", "xmlhttp_request"),
            ("JSONAPIResponse", "jsonapi_response"),
            ("HTTPSConnection", "https_connection"),
            ("URLParser", "url_parser"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_real_world_examples(self):
        """Test normalizing real-world function names."""
        test_cases = [
            ("calculateTotalPrice", "calculate_total_price"),
            ("getUserProfile", "get_user_profile"),
            ("sendHTTPRequest", "send_http_request"),
            ("parseJSONResponse", "parse_json_response"),
            ("validateEmailAddress", "validate_email_address"),
            ("generateUUIDString", "generate_uuid_string"),
            ("connectToDatabase", "connect_to_database"),
            ("processPaymentTransaction", "process_payment_transaction"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected

    def test_normalize_already_normalized_names(self):
        """Test that already normalized names remain unchanged."""
        test_cases = [
            ("already_normalized", "already_normalized"),
            ("snake_case_name", "snake_case_name"),
            ("simple_function", "simple_function"),
            ("get_user_data", "get_user_data"),
        ]

        for input_name, expected in test_cases:
            result = normalize_tool_name(input_name)
            assert result == expected
