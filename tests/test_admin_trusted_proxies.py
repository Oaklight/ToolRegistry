"""Trusted-proxy resolution for the admin auth throttle key (#431).

The throttle key must be the client the trusted proxy saw, not an address
the client can choose by prepending ``X-Forwarded-For`` entries.
"""

import urllib.error
import urllib.request
import time

import pytest

from toolregistry import ToolRegistry
from toolregistry._vendor.httpserver import Request
from toolregistry.admin.auth import (
    address_in_networks,
    forwarded_source,
    parse_trusted_proxies,
)
from toolregistry.admin.handlers import _client_source
from toolregistry.admin.server import AdminApp, AdminServer

TRUSTED_PEER = "127.0.0.1"
CLIENT = "198.51.100.9"


def _request(peer: str, forwarded: str | None, trusted=()) -> Request:
    app = AdminApp()
    app.trusted_proxies = parse_trusted_proxies(trusted)
    headers = {} if forwarded is None else {"x-forwarded-for": forwarded}
    return Request("GET", "/api/tools", "", headers, b"", (peer, 41000), app)


class TestParsing:
    def test_addresses_and_ranges_are_accepted(self) -> None:
        networks = parse_trusted_proxies(["127.0.0.1", "10.0.0.0/8", "::1"])
        assert address_in_networks("127.0.0.1", networks)
        assert address_in_networks("10.2.3.4", networks)
        assert address_in_networks("::1", networks)
        assert not address_in_networks("203.0.113.9", networks)

    def test_a_malformed_entry_is_refused(self) -> None:
        with pytest.raises(ValueError, match="not an IP address"):
            parse_trusted_proxies(["not-an-address"])
        with pytest.raises(ValueError, match="trusted proxy"):
            AdminServer(ToolRegistry(), port=0, trusted_proxies=["nope"])

    def test_a_mixed_family_comparison_is_false(self) -> None:
        networks = parse_trusted_proxies(["127.0.0.1"])
        assert not address_in_networks("::1", networks)


class TestForwardedChain:
    def test_a_single_hop_is_the_client(self) -> None:
        trusted = parse_trusted_proxies([TRUSTED_PEER])
        assert forwarded_source(CLIENT, trusted) == CLIENT

    def test_the_rightmost_untrusted_hop_is_the_client(self) -> None:
        trusted = parse_trusted_proxies([TRUSTED_PEER])
        # The client prepends a forged entry; the proxy appends the real one.
        assert forwarded_source(f"1.2.3.4, {CLIENT}", trusted) == CLIENT

    def test_trusted_intermediate_hops_are_skipped(self) -> None:
        trusted = parse_trusted_proxies([TRUSTED_PEER, "10.0.0.0/8"])
        header = "1.2.3.4, 10.0.0.5, 10.0.0.6"
        assert forwarded_source(header, trusted) == "1.2.3.4"

    def test_an_empty_chain_is_none(self) -> None:
        trusted = parse_trusted_proxies([TRUSTED_PEER])
        assert forwarded_source("", trusted) is None
        assert forwarded_source(" , ", trusted) is None

    def test_a_malformed_hop_makes_the_chain_unusable(self) -> None:
        trusted = parse_trusted_proxies([TRUSTED_PEER])
        assert forwarded_source("not-an-ip, 203.0.113.9", trusted) is None
        assert forwarded_source("203.0.113.9, also-bad", trusted) is None
        assert forwarded_source("203.0.113.9:443", trusted) is None

    def test_a_chain_of_trusted_hops_is_none(self) -> None:
        trusted = parse_trusted_proxies([TRUSTED_PEER, "10.0.0.0/8"])
        assert forwarded_source("10.0.0.5, 10.0.0.6", trusted) is None


class TestClientSource:
    def test_a_trusted_peer_uses_the_rightmost_untrusted_hop(self) -> None:
        request = _request(TRUSTED_PEER, f"{CLIENT}, 203.0.113.9", [TRUSTED_PEER])
        assert _client_source(request) == "203.0.113.9"

    def test_a_forged_leftmost_entry_cannot_choose_the_key(self) -> None:
        request = _request(TRUSTED_PEER, f"1.2.3.4, {CLIENT}", [TRUSTED_PEER])
        assert _client_source(request) == CLIENT

    def test_an_untrusted_peer_ignores_the_header(self) -> None:
        request = _request("203.0.113.50", "1.2.3.4", [TRUSTED_PEER])
        assert _client_source(request) == "203.0.113.50"

    def test_a_malformed_header_falls_back_to_the_peer(self) -> None:
        request = _request(TRUSTED_PEER, "not-an-ip", [TRUSTED_PEER])
        assert _client_source(request) == TRUSTED_PEER

    def test_an_empty_header_falls_back_to_the_peer(self) -> None:
        request = _request(TRUSTED_PEER, None, [TRUSTED_PEER])
        assert _client_source(request) == TRUSTED_PEER

    def test_no_trusted_proxies_keeps_the_peer(self) -> None:
        request = _request(TRUSTED_PEER, CLIENT)
        assert _client_source(request) == TRUSTED_PEER

    def test_an_unknown_peer_is_not_forwarded(self) -> None:
        app = AdminApp()
        app.trusted_proxies = parse_trusted_proxies([TRUSTED_PEER])
        request = Request(
            "GET", "/api/tools", "", {"x-forwarded-for": CLIENT}, b"", None, app
        )
        assert _client_source(request) == "unknown"


class TestServerWiring:
    def test_the_server_exposes_the_parsed_networks(self) -> None:
        server = AdminServer(
            ToolRegistry(), trusted_proxies=["127.0.0.1", "10.0.0.0/8"]
        )
        assert address_in_networks("10.1.2.3", server.trusted_proxies)

    def test_the_throttle_keys_on_the_forwarded_client(self) -> None:
        """Exhausting one forged source does not block another (#431)."""
        from toolregistry.admin.auth import AUTH_FAILURE_LIMIT

        server = AdminServer(
            ToolRegistry(),
            port=0,
            auth_token="correct-token",
            trusted_proxies=["127.0.0.1"],
        )
        try:
            info = server.start()
            time.sleep(0.1)
            url = f"{info.url}/api/tools"

            def attempt(source: str, token: str) -> int:
                request = urllib.request.Request(url)
                request.add_header("Authorization", f"Bearer {token}")
                request.add_header("X-Forwarded-For", source)
                try:
                    with urllib.request.urlopen(request, timeout=5) as response:
                        return response.status
                except urllib.error.HTTPError as error:
                    return error.code

            for _ in range(AUTH_FAILURE_LIMIT):
                assert attempt(CLIENT, "wrong") == 401
            assert attempt(CLIENT, "correct-token") == 429
            # Another client through the same trusted proxy is unaffected.
            assert attempt("203.0.113.77", "correct-token") == 200
        finally:
            server.stop()
