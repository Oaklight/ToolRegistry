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
    PrivateAddressError,
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
    state: dict[str, list] = {
        "addresses": [],
        "hosts": [],
        "ports": [],
        "calls": 0,
    }

    def _resolve(host, port):
        state["calls"] += 1
        state["hosts"].append(host)
        state["ports"].append(port)
        return list(state["addresses"])

    async def _resolve_async(host, port, timeout=0):
        state["calls"] += 1
        state["hosts"].append(host)
        state["ports"].append(port)
        return list(state["addresses"])

    monkeypatch.setattr(_netpolicy, "_resolve", _resolve)
    monkeypatch.setattr(_netpolicy, "_resolve_async", _resolve_async)
    clear_address_cache()
    return state


class TestLiteralAddresses:
    @pytest.mark.parametrize("host", PRIVATE_LITERALS)
    def test_private_literal_is_refused(self, host):
        with pytest.raises(UnsafeAddressError, match="non-public address"):
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


class TestWebSocketSchemes:
    """``ws``/``wss`` are checked natively, with no scheme translation (#407)."""

    @pytest.mark.parametrize(
        ("url", "port"),
        [("ws://example.com/socket", 80), ("wss://example.com/socket", 443)],
    )
    def test_scheme_passes_with_its_default_port(self, resolver, url, port):
        resolver["addresses"].append("93.184.216.34")
        assert validate_outbound_url(url) == url
        assert resolver["hosts"] == ["example.com"]
        assert resolver["ports"] == [port]

    def test_private_name_is_refused(self, resolver):
        resolver["addresses"].append("10.0.0.7")
        with pytest.raises(PrivateAddressError, match="non-public address"):
            validate_outbound_url("ws://internal.example/socket")

    def test_cache_key_includes_the_scheme(self, resolver):
        """A decision for ``https`` must not answer for ``wss``."""
        resolver["addresses"].append("93.184.216.34")
        validate_outbound_url("https://example.com/socket")
        resolver["addresses"][:] = ["10.0.0.7"]
        with pytest.raises(PrivateAddressError):
            validate_outbound_url("wss://example.com/socket")

    @pytest.mark.parametrize("scheme", ["file", "ftp", "gopher"])
    def test_other_schemes_are_still_refused(self, scheme):
        with pytest.raises(UnsafeAddressError, match="only http, https, ws and wss"):
            validate_outbound_url(f"{scheme}://example.com/socket")


class TestResolvedNames:
    def test_public_name_passes(self, resolver):
        resolver["addresses"].append("93.184.216.34")
        url = "https://example.com/spec"
        assert validate_outbound_url(url) == url

    def test_private_name_is_refused(self, resolver):
        resolver["addresses"].append("10.0.0.7")
        with pytest.raises(PrivateAddressError, match="non-public address") as excinfo:
            validate_outbound_url("https://internal.example/spec")

        assert excinfo.value.addresses == ("10.0.0.7",)

    def test_one_private_address_refuses_the_set(self, resolver):
        resolver["addresses"].extend(["93.184.216.34", "10.0.0.7"])
        with pytest.raises(PrivateAddressError, match="non-public address") as excinfo:
            validate_outbound_url("https://mixed.example/spec")

        assert excinfo.value.addresses == ("93.184.216.34", "10.0.0.7")

    def test_refusal_text_does_not_name_the_resolved_address(self, resolver):
        """A resolved address is topology; the exception carries it apart."""
        resolver["addresses"].append("10.0.0.7")
        with pytest.raises(PrivateAddressError) as excinfo:
            validate_outbound_url("https://internal.example/spec")

        text = str(excinfo.value)
        assert "internal.example" in text
        assert "10.0.0.7" not in text

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

    def test_async_websocket_scheme_passes(self, resolver):
        """The async path accepts ``wss`` and resolves on its own port."""
        resolver["addresses"].append("93.184.216.34")
        url = "wss://example.com/socket"
        assert asyncio.run(validate_outbound_url_async(url)) == url
        assert resolver["ports"] == [443]

    def test_async_resolver_timeout_is_refused(self, monkeypatch):
        async def timing_out(host, port, timeout=0):
            raise asyncio.TimeoutError()

        monkeypatch.setattr(_netpolicy, "_resolve_async", timing_out)
        clear_address_cache()
        with pytest.raises(UnsafeAddressError, match="Could not resolve"):
            asyncio.run(validate_outbound_url_async("https://slow.example/spec"))


#: One literal from each range the policy refuses explicitly.  Several are
#: reported as global by ``ipaddress``; the rest are pinned so an interpreter
#: table change cannot open them again.
SPECIAL_PURPOSE_LITERALS = [
    "192.0.0.1",  # IETF protocol assignments
    "192.88.99.1",  # 6to4 relay anycast, is_global=True
    "198.18.0.1",  # benchmarking
    "240.0.0.1",  # reserved
    "::7f00:1",  # IPv4-compatible, embeds 127.0.0.1
    "100::1",  # discard-only
    "2001::1",  # Teredo
    "2001:2::1",  # benchmarking
    "2001:10::1",  # ORCHID
    "2001:20::1",  # ORCHIDv2, is_global=True
    "2001:db8::1",  # documentation
    "2002::1",  # 6to4, embeds an IPv4 address
    "3fff::1",  # documentation
    "5f00::1",  # SRv6 SIDs, is_global=True
    "ff02::1",  # IPv6 multicast
    "64:ff9b:1::808:808",  # NAT64 local-use prefix, refused as a whole
]


class TestSpecialPurposeRanges:
    @pytest.mark.parametrize("host", SPECIAL_PURPOSE_LITERALS)
    def test_special_purpose_literal_is_refused(self, host):
        with pytest.raises(PrivateAddressError):
            validate_outbound_url(_url(host))

    @pytest.mark.parametrize("host", SPECIAL_PURPOSE_LITERALS)
    def test_allow_private_hosts_still_opts_out(self, host):
        url = _url(host)
        assert validate_outbound_url(url, allow_private_hosts=True) == url


#: Vectors for the NAT64 local-use prefix.  The first one is the reviewer's:
#: under the RFC 6052 /48 layout, bits 48-63 (0x7f00) and bits 72-87 (0x0100)
#: encode 127.0.0.1, while the low 32 bits (8.8.8.8) are a decoy.
LOCAL_USE_VECTORS = [
    "64:ff9b:1:7f00:0:100:808:808",
    "64:ff9b:1::808:808",
]


class TestNat64:
    """The well-known prefix is unwrapped; the local-use prefix is refused."""

    def test_well_known_prefix_embedded_loopback_is_refused(self):
        # 64:ff9b::7f00:1 reaches 127.0.0.1; is_global reports the prefix as
        # public, which is the bypass this check closes.
        with pytest.raises(PrivateAddressError):
            validate_outbound_url(_url("64:ff9b::7f00:1"))

    def test_well_known_prefix_embedded_public_address_is_allowed(self):
        url = _url("64:ff9b::808:808")  # 8.8.8.8
        assert validate_outbound_url(url) == url

    @pytest.mark.parametrize("host", LOCAL_USE_VECTORS)
    def test_local_use_prefix_is_refused_as_a_whole(self, host):
        with pytest.raises(PrivateAddressError):
            validate_outbound_url(_url(host))

    @pytest.mark.parametrize("host", LOCAL_USE_VECTORS)
    def test_local_use_prefix_opt_out_still_allows(self, host):
        url = _url(host)
        assert validate_outbound_url(url, allow_private_hosts=True) == url


class TestPublicModule:
    """``toolregistry.netpolicy`` is the public name for the policy."""

    def test_public_names_are_the_compatibility_names(self):
        from toolregistry import _netpolicy, netpolicy

        assert netpolicy.validate_outbound_url is _netpolicy.validate_outbound_url
        assert (
            netpolicy.validate_outbound_url_async
            is _netpolicy.validate_outbound_url_async
        )
        assert netpolicy.UnsafeAddressError is _netpolicy.UnsafeAddressError
        assert netpolicy.PrivateAddressError is _netpolicy.PrivateAddressError
        assert netpolicy.SCHEMES is _netpolicy.SCHEMES
        assert netpolicy.clear_address_cache is _netpolicy.clear_address_cache

    def test_public_import_enforces_the_policy(self):
        from toolregistry.netpolicy import PrivateAddressError as PublicError
        from toolregistry.netpolicy import validate_outbound_url as public_validate

        with pytest.raises(PublicError):
            public_validate("http://127.0.0.1/")
