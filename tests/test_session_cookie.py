"""Tests for SessionCookie and cookie-based admin auth."""

import time


from toolregistry.admin.auth import SessionCookie


class TestSessionCookie:
    def test_issue_and_verify(self):
        sc = SessionCookie(max_age=60)
        token = sc.issue()
        assert sc.verify(token)

    def test_expired_token_rejected(self):
        sc = SessionCookie(max_age=1)
        token = sc.issue()
        time.sleep(1.5)
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
