"""Async base-URL client must not resolve names on the event loop (#406).

``_BaseUrlAsyncClient`` carries a request to a configured origin, so it
checks that origin against the outbound address policy before every call.
That check resolves the host, which is blocking work; the async client must
await the async resolver instead of calling the synchronous one on the loop.
The autouse fixture in ``conftest.py`` stubs both resolvers for the rest of
the suite, and each test here re-stubs them to control the answer.
"""

import asyncio

import pytest

from toolregistry import _netpolicy
from toolregistry._netpolicy import UnsafeAddressError, clear_address_cache
from toolregistry.utils import _BaseUrlAsyncClient

BASE_URL = "https://api.example.test"
PUBLIC_ADDRESS = "93.184.216.34"


def _fail_sync_resolve(host, port):
    """Stand-in for the synchronous resolver: calling it is the bug."""
    raise AssertionError("the synchronous resolver ran on the event loop")


class _RecordingAsyncClient:
    """Minimal async client that records the URL it was asked to fetch."""

    def __init__(self):
        self.urls = []
        self.closed = False

    async def get(self, url, **kwargs):
        self.urls.append(url)
        return url

    async def request(self, method, url, **kwargs):
        self.urls.append(url)
        return url

    async def post(self, url, **kwargs):
        self.urls.append(url)
        return url

    async def put(self, url, **kwargs):
        self.urls.append(url)
        return url

    async def patch(self, url, **kwargs):
        self.urls.append(url)
        return url

    async def delete(self, url, **kwargs):
        self.urls.append(url)
        return url

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_url_uses_the_async_resolver_only(monkeypatch):
    """A cache miss must not fall back to the synchronous resolver."""
    clear_address_cache()
    calls = []

    async def _resolve_async(host, port, timeout=0):
        calls.append((host, port))
        return [PUBLIC_ADDRESS]

    monkeypatch.setattr(_netpolicy, "_resolve", _fail_sync_resolve)
    monkeypatch.setattr(_netpolicy, "_resolve_async", _resolve_async)

    client = _BaseUrlAsyncClient(_RecordingAsyncClient(), BASE_URL)

    assert await client._url("/pets") == f"{BASE_URL}/pets"
    assert calls == [("api.example.test", 443)]


@pytest.mark.asyncio
async def test_concurrent_first_requests_do_not_stall_the_loop(monkeypatch):
    """Cold concurrent calls leave the loop free while the name resolves."""
    clear_address_cache()
    state = {"resolving": False, "ticks_while_resolving": 0}

    async def _slow_resolve_async(host, port, timeout=0):
        state["resolving"] = True
        await asyncio.sleep(0.05)
        state["resolving"] = False
        return [PUBLIC_ADDRESS]

    async def _heartbeat():
        while True:
            if state["resolving"]:
                state["ticks_while_resolving"] += 1
            await asyncio.sleep(0.005)

    monkeypatch.setattr(_netpolicy, "_resolve", _fail_sync_resolve)
    monkeypatch.setattr(_netpolicy, "_resolve_async", _slow_resolve_async)

    client = _BaseUrlAsyncClient(_RecordingAsyncClient(), BASE_URL)
    heartbeat = asyncio.create_task(_heartbeat())
    try:
        urls = await asyncio.gather(*(client._url(f"/pets/{i}") for i in range(5)))
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)

    assert urls == [f"{BASE_URL}/pets/{i}" for i in range(5)]
    assert state["ticks_while_resolving"] > 0


@pytest.mark.asyncio
async def test_requests_await_the_address_check(monkeypatch):
    """Every verb goes through the awaited check before it reaches the client."""
    clear_address_cache()

    async def _resolve_async(host, port, timeout=0):
        return ["10.0.0.5"]

    monkeypatch.setattr(_netpolicy, "_resolve", _fail_sync_resolve)
    monkeypatch.setattr(_netpolicy, "_resolve_async", _resolve_async)

    recording = _RecordingAsyncClient()
    client = _BaseUrlAsyncClient(recording, BASE_URL)

    with pytest.raises(UnsafeAddressError):
        await client.get("/pets")
    with pytest.raises(UnsafeAddressError):
        await client.request("DELETE", "/pets/1")
    assert recording.urls == []


@pytest.mark.asyncio
async def test_requests_pass_the_joined_url(monkeypatch):
    """A public origin reaches the underlying client as base plus path."""
    clear_address_cache()

    async def _resolve_async(host, port, timeout=0):
        return [PUBLIC_ADDRESS]

    monkeypatch.setattr(_netpolicy, "_resolve", _fail_sync_resolve)
    monkeypatch.setattr(_netpolicy, "_resolve_async", _resolve_async)

    recording = _RecordingAsyncClient()
    client = _BaseUrlAsyncClient(recording, BASE_URL)

    assert await client.get("/pets") == f"{BASE_URL}/pets"
    assert await client.post("/pets") == f"{BASE_URL}/pets"
    assert recording.urls == [f"{BASE_URL}/pets", f"{BASE_URL}/pets"]
