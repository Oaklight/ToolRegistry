"""Tests for the outbound address policy (#370).

The resolver is replaced everywhere: the policy decides on addresses, and a
unit test must not depend on real DNS.  The autouse fixture in
``conftest.py`` already stubs it for the rest of the suite; these tests stub
it again so they can choose the answer.
"""

import asyncio
import socket

import pytest

from toolregistry import _netpolicy
from toolregistry._netpolicy import (
    UnsafeAddressError,
    clear_address_cache,
    validate_outbound_url,
    validate_outbound_url_async,
)

PRIVATE_LITERALS = [
    "127.0.0.1",
    "::1",
    "169.254.169.254",
    "fe80::1",
    "10.1.2.3",
    "172.16.4.5",
    "192.168.1.10",
    "100.64.0.1",
    "0.0.0.0",
    "::",
    "224.0.0.1",
    "::ffff:127.0.0.1",
]

PUBLIC_LITERALS = ["8.8.8.8", "2001:4860::1", "::ffff:8.8.8.8"]


def _url(host: str) -> str:
    """Build a URL for *host*, bracketing an IPv6 literal."""
    if ":" in host:
        return f"https://[{host}]/spec"
    return f"https://{host}/spec"


@pytest.fixture
def resolver(monkeypatch):
    """Replace the resolver with a controllable one (sync and async)."""
    state: dict[str, list] = {"addresses": [], "hosts": [], "calls": 0}

    def _resolve(host, port):
        state["calls"] += 1
        state["hosts"].append(host)
        return list(state["addresses"])

    async def _resolve_async(host, port, timeout=0):
        state["calls"] += 1
        state["hosts"].append(host)
        return list(state["addresses"])

    monkeypatch.setattr(_netpolicy, "_resolve", _resolve)
    monkeypatch.setattr(_netpolicy, "_resolve_async", _resolve_async)
    clear_address_cache()
    return state


class TestLiteralAddresses:
    @pytest.mark.parametrize("host", PRIVATE_LITERALS)
    def test_private_literal_is_refused(self, host):
        with pytest.raises(UnsafeAddressError, match="not a public address"):
            validate_outbound_url(_url(host))

    @pytest.mark.parametrize("host", PUBLIC_LITERALS)
    def test_public_literal_passes(self, host):
        url = _url(host)
        assert validate_outbound_url(url) == url

    def test_allow_private_hosts_skips_the_check(self):
        url = "http://127.0.0.1:8080/x"
        assert validate_outbound_url(url, allow_private_hosts=True) == url

    def test_non_http_scheme_is_refused(self):
        with pytest.raises(UnsafeAddressError, match="scheme"):
            validate_outbound_url("file:///etc/hostname")

    def test_missing_host_is_refused(self):
        with pytest.raises(UnsafeAddressError, match="host"):
            validate_outbound_url("https:///spec")


class TestResolvedNames:
    def test_public_name_passes(self, resolver):
        resolver["addresses"].append("93.184.216.34")
        url = "https://example.com/spec"
        assert validate_outbound_url(url) == url

    def test_private_name_is_refused(self, resolver):
        resolver["addresses"].append("10.0.0.7")
        with pytest.raises(UnsafeAddressError, match="10.0.0.7"):
            validate_outbound_url("https://internal.example/spec")

    def test_one_private_address_refuses_the_set(self, resolver):
        resolver["addresses"].extend(["93.184.216.34", "10.0.0.7"])
        with pytest.raises(UnsafeAddressError, match="10.0.0.7"):
            validate_outbound_url("https://mixed.example/spec")

    def test_empty_answer_is_refused(self, resolver):
        with pytest.raises(UnsafeAddressError, match="no address"):
            validate_outbound_url("https://empty.example/spec")

    def test_resolution_failure_is_refused_and_not_cached(self, monkeypatch):
        calls: list[str] = []

        def failing(host, port):
            calls.append(host)
            raise socket.gaierror("temporary failure in name resolution")

        monkeypatch.setattr(_netpolicy, "_resolve", failing)
        clear_address_cache()
        with pytest.raises(UnsafeAddressError, match="Could not resolve"):
            validate_outbound_url("https://flaky.example/spec")

        # A failure must not be remembered: the next call resolves again.
        monkeypatch.setattr(
            _netpolicy, "_resolve", lambda host, port: ["93.184.216.34"]
        )
        assert validate_outbound_url("https://flaky.example/spec")
        assert calls == ["flaky.example"]

    def test_success_is_cached(self, resolver):
        resolver["addresses"].append("93.184.216.34")
        validate_outbound_url("https://example.com/spec")
        validate_outbound_url("https://example.com/spec")
        assert resolver["calls"] == 1

    def test_clearing_the_cache_forces_a_new_lookup(self, resolver):
        resolver["addresses"].append("93.184.216.34")
        validate_outbound_url("https://example.com/spec")
        clear_address_cache()
        validate_outbound_url("https://example.com/spec")
        assert resolver["calls"] == 2

    def test_trailing_dot_is_normalised(self, resolver):
        resolver["addresses"].append("93.184.216.34")
        validate_outbound_url("https://example.com./spec")
        assert resolver["hosts"] == ["example.com"]

    def test_allow_private_hosts_does_not_resolve(self, resolver):
        url = "https://internal.example/spec"
        assert validate_outbound_url(url, allow_private_hosts=True) == url
        assert resolver["calls"] == 0


class TestAsync:
    def test_async_private_literal_is_refused(self):
        with pytest.raises(UnsafeAddressError):
            asyncio.run(validate_outbound_url_async("https://127.0.0.1/spec"))

    def test_async_uses_the_loop_resolver(self, resolver):
        resolver["addresses"].append("10.0.0.7")
        with pytest.raises(UnsafeAddressError):
            asyncio.run(validate_outbound_url_async("https://internal.example/spec"))
        assert resolver["calls"] == 1

    def test_async_resolver_timeout_is_refused(self, monkeypatch):
        async def timing_out(host, port, timeout=0):
            raise asyncio.TimeoutError()

        monkeypatch.setattr(_netpolicy, "_resolve_async", timing_out)
        clear_address_cache()
        with pytest.raises(UnsafeAddressError, match="Could not resolve"):
            asyncio.run(validate_outbound_url_async("https://slow.example/spec"))
