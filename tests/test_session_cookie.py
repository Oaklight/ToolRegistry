"""Tests for SessionCookie and cookie-based admin auth."""

import time
from unittest.mock import patch

import pytest

from toolregistry.admin.auth import SessionCookie


class TestSessionCookie:
    def test_issue_and_verify(self):
        sc = SessionCookie(max_age=60)
        token = sc.issue()
        assert sc.verify(token)

    def test_expired_token_rejected(self):
        sc = SessionCookie(max_age=10)
        token = sc.issue()
        with patch("toolregistry.admin.auth.time") as mock_time:
            mock_time.time.return_value = time.time() + 20
            assert not sc.verify(token)

    def test_tampered_signature_rejected(self):
        sc = SessionCookie()
        token = sc.issue()
        ts, sig = token.split(".", 1)
        tampered = f"{ts}.{'a' * len(sig)}"
        assert not sc.verify(tampered)

    def test_malformed_token_rejected(self):
        sc = SessionCookie()
        assert not sc.verify("")
        assert not sc.verify("no-dot-here")
        assert not sc.verify("abc.def")

    def test_different_secrets_incompatible(self):
        sc1 = SessionCookie(secret="secret1")
        sc2 = SessionCookie(secret="secret2")
        token = sc1.issue()
        assert sc1.verify(token)
        assert not sc2.verify(token)

    def test_custom_cookie_name(self):
        sc = SessionCookie(cookie_name="my_session")
        assert sc.cookie_name == "my_session"

    def test_default_cookie_name(self):
        sc = SessionCookie()
        assert sc.cookie_name == "tr_session"

    def test_default_max_age(self):
        sc = SessionCookie()
        assert sc.max_age == 3600


class TestAdminCookieFlow:
    """Integration test for Bearer → cookie → cookie-only auth flow."""

    @pytest.fixture()
    def server(self):
        from toolregistry import ToolRegistry
        from toolregistry.admin import AdminServer

        registry = ToolRegistry()
        registry.register(lambda x: x, name="echo", description="echo")
        srv = AdminServer(registry, auth_token="test-token-123")
        info = srv.start()
        yield info, srv
        srv.stop()

    def test_bearer_sets_cookie_and_cookie_authenticates(self, server):
        import http.client
        import json

        info, srv = server
        host, port = info.url.replace("http://", "").split(":")

        # 1. Bearer auth — should get Set-Cookie in response
        conn = http.client.HTTPConnection(host, int(port))
        conn.request(
            "GET",
            "/api/tools",
            headers={"Authorization": f"Bearer {info.token}"},
        )
        resp = conn.getresponse()
        assert resp.status == 200
        set_cookie = resp.getheader("Set-Cookie")
        assert set_cookie is not None
        assert "tr_session=" in set_cookie

        # Extract cookie value
        cookie_val = set_cookie.split("tr_session=")[1].split(";")[0]

        # 2. Cookie-only auth — no Bearer header
        conn2 = http.client.HTTPConnection(host, int(port))
        conn2.request(
            "GET",
            "/api/tools",
            headers={"Cookie": f"tr_session={cookie_val}"},
        )
        resp2 = conn2.getresponse()
        assert resp2.status == 200
        body = json.loads(resp2.read())
        assert "tools" in body

        # 3. No auth at all — should fail
        conn3 = http.client.HTTPConnection(host, int(port))
        conn3.request("GET", "/api/tools")
        resp3 = conn3.getresponse()
        assert resp3.status == 401

    def test_cookie_sliding_window(self, server):
        import http.client

        info, srv = server
        host, port = info.url.replace("http://", "").split(":")

        # Get initial cookie via Bearer
        conn = http.client.HTTPConnection(host, int(port))
        conn.request(
            "GET",
            "/api/tools",
            headers={"Authorization": f"Bearer {info.token}"},
        )
        resp = conn.getresponse()
        resp.read()
        cookie1 = resp.getheader("Set-Cookie").split("tr_session=")[1].split(";")[0]

        # Use cookie — should get a refreshed cookie back
        conn2 = http.client.HTTPConnection(host, int(port))
        conn2.request(
            "GET",
            "/api/tools",
            headers={"Cookie": f"tr_session={cookie1}"},
        )
        resp2 = conn2.getresponse()
        resp2.read()
        set_cookie2 = resp2.getheader("Set-Cookie")
        assert set_cookie2 is not None
        assert "tr_session=" in set_cookie2
