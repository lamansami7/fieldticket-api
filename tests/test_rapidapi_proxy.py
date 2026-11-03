import pytest
from fastapi import HTTPException

from rapidapi_proxy import verified_rapidapi_subscriber


def test_unconfigured_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("RAPIDAPI_PROXY_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        verified_rapidapi_subscriber("attacker", "some-user")
    assert exc.value.status_code == 503


def test_forged_subscriber_header_is_rejected(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_PROXY_SECRET", "server-only-secret")
    with pytest.raises(HTTPException) as exc:
        verified_rapidapi_subscriber(None, "forged-user")
    assert exc.value.status_code == 401


def test_wrong_proxy_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_PROXY_SECRET", "server-only-secret")
    with pytest.raises(HTTPException) as exc:
        verified_rapidapi_subscriber("wrong-secret", "subscriber")
    assert exc.value.status_code == 401


def test_missing_identity_is_rejected(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_PROXY_SECRET", "server-only-secret")
    with pytest.raises(HTTPException) as exc:
        verified_rapidapi_subscriber("server-only-secret", None)
    assert exc.value.status_code == 401


def test_verified_subscriber(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_PROXY_SECRET", "server-only-secret")
    assert verified_rapidapi_subscriber("server-only-secret", " subscriber ") == "subscriber"
