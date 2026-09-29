from __future__ import annotations

import base64
import json
import time

import pytest
import requests

from ddpe.connect.auth import KeycloakAuthenticator
from ddpe.connect.config import load_config
from ddpe.connect.errors import DDPEAuthenticationError


def _config(**overrides):
    values = {
        "spark_connect_url": "spark.example:443",
        "token_url": "https://keycloak.example/token",
        "client_id": "client",
        "client_secret": "secret",
        "username": "user",
        "password": "password",
    }
    values.update(overrides)
    return load_config(overrides=values, environ={})


class Response:
    ok = True
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def _jwt(exp):
    encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    return f"{encode({'alg': 'none'})}.{encode({'exp': exp})}."


def test_password_grant_and_cache(monkeypatch):
    calls = []
    token = _jwt(time.time() + 3600)

    def post(*args, **kwargs):
        calls.append(kwargs)
        return Response({"access_token": token, "expires_in": 300})

    monkeypatch.setattr(requests, "post", post)
    auth = KeycloakAuthenticator(_config())
    assert auth.get_token() == token
    assert auth.get_token() == token
    assert len(calls) == 1
    assert calls[0]["data"]["grant_type"] == "password"
    assert calls[0]["verify"] is True


def test_force_refresh_requests_another_token(monkeypatch):
    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: Response({"access_token": "opaque", "expires_in": 300}),
    )
    auth = KeycloakAuthenticator(_config())
    auth.get_token()
    count = {"value": 0}

    def post(*args, **kwargs):
        count["value"] += 1
        return Response({"access_token": "new", "expires_in": 300})

    monkeypatch.setattr(requests, "post", post)
    assert auth.get_token(force_refresh=True) == "new"
    assert count["value"] == 1


def test_direct_access_token_skips_keycloak(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: pytest.fail("unexpected call"))
    assert KeycloakAuthenticator(_config(access_token="direct")).get_token() == "direct"


def test_network_error_is_wrapped(monkeypatch):
    def post(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(DDPEAuthenticationError, match="Unable to contact"):
        KeycloakAuthenticator(_config()).get_token()


def test_rejected_credentials_do_not_leak_response(monkeypatch):
    response = Response({"error": "invalid_grant", "secret": "do-not-print"})
    response.ok = False
    response.status_code = 401
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: response)
    with pytest.raises(DDPEAuthenticationError, match="invalid_grant") as captured:
        KeycloakAuthenticator(_config()).get_token()
    assert "do-not-print" not in str(captured.value)


def test_missing_access_token_is_rejected(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Response({}))
    with pytest.raises(DDPEAuthenticationError, match="access_token"):
        KeycloakAuthenticator(_config()).get_token()


def test_keycloak_uses_its_own_ca_not_the_spark_ca(monkeypatch, tmp_path):
    spark_ca = tmp_path / "spark-ca.pem"
    keycloak_ca = tmp_path / "keycloak-ca.pem"
    spark_ca.write_text("spark-ca", encoding="utf-8")
    keycloak_ca.write_text("keycloak-ca", encoding="utf-8")
    calls = []

    def post(*args, **kwargs):
        calls.append(kwargs)
        return Response({"access_token": "token", "expires_in": 300})

    monkeypatch.setattr(requests, "post", post)
    auth = KeycloakAuthenticator(
        _config(
            spark_connect_ca=str(spark_ca),
            keycloak_ca=str(keycloak_ca),
        )
    )
    assert auth.get_token() == "token"
    assert calls[0]["verify"] == str(keycloak_ca)
    assert calls[0]["verify"] != str(spark_ca)
