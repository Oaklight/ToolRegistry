"""Tests for cookie support in HttpClientConfig."""

import pickle


from toolregistry.utils import HttpClientConfig


class TestHttpClientConfigCookies:
    """Test cookie parameter on HttpClientConfig."""

    def test_default_cookies_none(self):
        config = HttpClientConfig(base_url="https://example.com")
        assert config.cookies is None

    def test_cookies_stored(self):
        cookies = {"session_id": "abc123", "csrf": "xyz"}
        config = HttpClientConfig(base_url="https://example.com", cookies=cookies)
        assert config.cookies == cookies

    def test_cookies_in_client_kwargs(self):
        cookies = {"JSESSIONID": "abc"}
        config = HttpClientConfig(base_url="https://example.com", cookies=cookies)
        kwargs = config._client_kwargs()
        assert kwargs["cookies"] == cookies

    def test_no_cookies_in_client_kwargs(self):
        config = HttpClientConfig(base_url="https://example.com")
        kwargs = config._client_kwargs()
        assert kwargs["cookies"] is None

    def test_cookies_passed_to_sync_client(self):
        cookies = {"session": "test123"}
        config = HttpClientConfig(base_url="https://example.com", cookies=cookies)
        client = config.to_client(use_async=False)
        assert client._client._cookies == cookies

    def test_cookies_passed_to_async_client(self):
        cookies = {"session": "test123"}
        config = HttpClientConfig(base_url="https://example.com", cookies=cookies)
        client = config.to_client(use_async=True)
        assert client._client._cookies == cookies

    def test_persistent_client_preserves_cookies(self):
        cookies = {"session": "persistent"}
        config = HttpClientConfig(base_url="https://example.com", cookies=cookies)
        client1 = config.get_persistent_client(use_async=False)
        client2 = config.get_persistent_client(use_async=False)
        assert client1 is client2
        assert client1._client._cookies == cookies


class TestHttpClientConfigCookiesPickle:
    """Test that cookies survive pickling (for ProcessPoolBackend)."""

    def test_pickle_preserves_cookies(self):
        cookies = {"JSESSIONID": "abc123"}
        config = HttpClientConfig(base_url="https://example.com", cookies=cookies)
        restored = pickle.loads(pickle.dumps(config))
        assert restored.cookies == cookies
        assert restored.base_url == "https://example.com"

    def test_pickle_none_cookies(self):
        config = HttpClientConfig(base_url="https://example.com")
        restored = pickle.loads(pickle.dumps(config))
        assert restored.cookies is None

    def test_pickle_backward_compat(self):
        """Old pickled state without cookies key should work."""
        config = HttpClientConfig(base_url="https://example.com")
        state = config.__getstate__()
        del state["cookies"]
        config2 = HttpClientConfig.__new__(HttpClientConfig)
        config2.__setstate__(state)
        assert config2.cookies is None
