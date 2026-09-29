"""Keycloak authentication and process-local access-token caching."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import Any
import base64
import json
import time
import warnings

import requests
from urllib3.exceptions import InsecureRequestWarning

from .config import DDPEConfig
from .errors import DDPEAuthenticationError


@dataclass(frozen=True, slots=True)
class _Token:
    value: str
    expires_at: float


class TokenCache:
    """Thread-safe in-memory cache; tokens are never persisted."""

    _items: dict[tuple[str, ...], _Token] = {}
    _lock = Lock()

    @classmethod
    def get(cls, key: tuple[str, ...], skew_seconds: int) -> str | None:
        with cls._lock:
            item = cls._items.get(key)
            if item and item.expires_at - skew_seconds > time.time():
                return item.value
            cls._items.pop(key, None)
            return None

    @classmethod
    def put(cls, key: tuple[str, ...], value: str, expires_at: float) -> None:
        with cls._lock:
            cls._items[key] = _Token(value=value, expires_at=expires_at)

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._items.clear()


def _jwt_exp(token: str) -> float | None:
    """Read an unverified JWT expiry for cache management only."""

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return float(data["exp"]) if "exp" in data else None
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _cache_key(config: DDPEConfig) -> tuple[str, ...]:
    credential_fingerprint = sha256(
        f"{config.client_secret}\0{config.password}".encode()
    ).hexdigest()
    return (
        config.token_url,
        config.client_id,
        config.username,
        config.scope,
        credential_fingerprint,
    )


def _safe_server_error(response: requests.Response) -> str:
    try:
        payload: dict[str, Any] = response.json()
    except ValueError:
        return "non-JSON response"
    value = payload.get("error_description") or payload.get("error") or "request rejected"
    return str(value)[:300]


class KeycloakAuthenticator:
    """Acquire password-grant access tokens from Keycloak."""

    def __init__(self, config: DDPEConfig):
        self._config = config

    def get_token(self, *, force_refresh: bool = False) -> str:
        if self._config.access_token:
            return self._config.access_token

        key = _cache_key(self._config)
        if not force_refresh:
            cached = TokenCache.get(key, self._config.refresh_skew_seconds)
            if cached:
                return cached

        warning_context = warnings.catch_warnings() if self._config.verify_ssl is False else nullcontext()
        try:
            with warning_context:
                if self._config.verify_ssl is False:
                    warnings.simplefilter("ignore", InsecureRequestWarning)
                response = requests.post(
                    self._config.token_url,
                    data={
                        "grant_type": "password",
                        "client_id": self._config.client_id,
                        "client_secret": self._config.client_secret,
                        "username": self._config.username,
                        "password": self._config.password,
                        "scope": self._config.scope,
                    },
                    headers={"Accept": "application/json"},
                    timeout=self._config.timeout_seconds,
                    verify=self._config.verify_ssl,
                )
        except requests.RequestException as exc:
            raise DDPEAuthenticationError(
                f"Unable to contact the Keycloak token endpoint: {exc}"
            ) from exc

        if not response.ok:
            raise DDPEAuthenticationError(
                f"Keycloak authentication failed (HTTP {response.status_code}): "
                f"{_safe_server_error(response)}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise DDPEAuthenticationError("Keycloak returned invalid JSON.") from exc

        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise DDPEAuthenticationError("Keycloak did not return an access_token.")
        try:
            expires_in = float(payload.get("expires_in", 300))
        except (TypeError, ValueError):
            expires_in = 300.0
        expires_at = _jwt_exp(token) or (time.time() + max(expires_in, 1.0))
        TokenCache.put(key, token, expires_at)
        return token
