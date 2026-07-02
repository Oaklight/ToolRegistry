"""Tests for cloudpickle serialization of tool wrappers (#189)."""

import pickle

import cloudpickle
import pytest

from toolregistry.utils import HttpClientConfig


class TestHttpClientConfigPickle:
    def test_pickle_fresh(self):
        """Config with no active clients pickles cleanly."""
        cfg = HttpClientConfig(
            "http://api.example.com",
            headers={"Authorization": "Bearer token"},
            timeout=30.0,
        )
        data = cloudpickle.dumps(cfg)
        cfg2 = pickle.loads(data)  # noqa: S301
        assert cfg2.base_url == "http://api.example.com"
        assert cfg2.headers == {"Authorization": "Bearer token"}
        assert cfg2.timeout == 30.0
        assert cfg2._sync_client is None
        assert cfg2._async_client is None

    def test_pickle_after_persistent_client(self):
        """Config with active persistent client pickles by dropping client."""
        cfg = HttpClientConfig("http://api.example.com")
        cfg.get_persistent_client(use_async=False)
        assert cfg._sync_client is not None

        data = cloudpickle.dumps(cfg)
        cfg2 = pickle.loads(data)  # noqa: S301
        assert cfg2.base_url == "http://api.example.com"
        assert cfg2._sync_client is None  # dropped

        # Clean up
        cfg.close()

    def test_pickle_preserves_extra_options(self):
        cfg = HttpClientConfig(
            "http://api.example.com", verify=False, proxy="http://proxy"
        )
        data = cloudpickle.dumps(cfg)
        cfg2 = pickle.loads(data)  # noqa: S301
        assert cfg2.extra_options == {"verify": False, "proxy": "http://proxy"}

    def test_pickle_preserves_auth(self):
        cfg = HttpClientConfig("http://api.example.com", auth=("user", "pass"))
        data = cloudpickle.dumps(cfg)
        cfg2 = pickle.loads(data)  # noqa: S301
        assert cfg2.auth == ("user", "pass")


# MCPConnectionManager tests require the mcp package — guarded import
try:
    from toolregistry.integrations.mcp.connection import MCPConnectionManager

    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False


@pytest.mark.skipif(not _HAS_MCP, reason="mcp package not installed")
class TestMCPConnectionManagerPickle:
    def test_pickle_fresh(self):
        """Fresh manager (no connection) pickles cleanly."""
        mgr = MCPConnectionManager(
            "http://localhost:8000/mcp",
            headers={"X-Key": "val"},
            persistent=True,
        )
        data = cloudpickle.dumps(mgr)
        mgr2 = pickle.loads(data)  # noqa: S301
        assert mgr2._transport == "http://localhost:8000/mcp"
        assert mgr2._headers == {"X-Key": "val"}
        assert mgr2._persistent is True
        assert mgr2._client is None

    def test_pickle_preserves_transport_dict(self):
        """Dict transport config survives pickling."""
        transport = {"command": "python", "args": ["-m", "my_server"]}
        mgr = MCPConnectionManager(transport, persistent=False)
        data = cloudpickle.dumps(mgr)
        mgr2 = pickle.loads(data)  # noqa: S301
        assert mgr2._transport == transport
        assert mgr2._persistent is False
