"""Configuration loading from TOML, environment, and builder overrides."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
import os
import tomllib

from .errors import DDPEConfigurationError

DEFAULT_CONFIG_FILE = Path.home() / ".config" / "ddpe" / "config.toml"

_DEFAULTS: dict[str, Any] = {
    "spark_connect_url": None,
    "spark_connect_ca": None,
    "token_url": "http://localhost:8080/realms/ddpe/protocol/openid-connect/token",
    "client_id": "ddpe-client",
    "client_secret": "",
    "username": "",
    "password": "",
    "scope": "openid",
    "keycloak_ca": None,
    "verify_ssl": True,
    "timeout_seconds": 30.0,
    "refresh_skew_seconds": 60,
    "access_token": None,
}

_ENV: dict[str, str] = {
    "spark_connect_url": "DDPE_SPARK_CONNECT_URL",
    "spark_connect_ca": "DDPE_SPARK_CONNECT_CA",
    "token_url": "DDPE_KEYCLOAK_TOKEN_URL",
    "client_id": "DDPE_OIDC_CLIENT_ID",
    "client_secret": "DDPE_OIDC_CLIENT_SECRET",
    "username": "DDPE_USERNAME",
    "password": "DDPE_PASSWORD",
    "scope": "DDPE_OIDC_SCOPE",
    "keycloak_ca": "DDPE_KEYCLOAK_CA",
    "verify_ssl": "DDPE_VERIFY_SSL",
    "timeout_seconds": "DDPE_AUTH_TIMEOUT_SECONDS",
    "refresh_skew_seconds": "DDPE_TOKEN_REFRESH_SKEW_SECONDS",
    "access_token": "DDPE_ACCESS_TOKEN",
}


def _parse_verify_ssl(value: Any) -> bool | str:
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    text = str(value).strip()
    lowered = text.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    if not text:
        raise DDPEConfigurationError("verify_ssl cannot be empty.")
    return str(Path(text).expanduser())


def _read_toml(path: Path, *, required: bool) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise DDPEConfigurationError(f"Configuration file not found: {path}")
        return {}
    if not path.is_file():
        raise DDPEConfigurationError(f"Configuration path is not a file: {path}")
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise DDPEConfigurationError(f"Unable to read configuration file {path}: {exc}") from exc
    ddpe = document.get("ddpe", {})
    if not isinstance(ddpe, dict):
        raise DDPEConfigurationError("The [ddpe] TOML section must be a table.")
    auth = ddpe.pop("auth", {})
    spark = ddpe.pop("spark", {})
    if not isinstance(auth, dict) or not isinstance(spark, dict):
        raise DDPEConfigurationError("The [ddpe.auth] and [ddpe.spark] sections must be tables.")
    return {**ddpe, **auth, "spark_config": spark}


@dataclass(frozen=True, slots=True)
class DDPEConfig:
    """Resolved DDPE client configuration."""

    spark_connect_url: str
    spark_connect_ca: str | None
    token_url: str
    client_id: str
    client_secret: str
    username: str
    password: str
    scope: str
    keycloak_ca: str | None
    verify_ssl: bool | str
    timeout_seconds: float
    refresh_skew_seconds: int
    access_token: str | None = None
    spark_config: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if "spark.app.name" in self.spark_config:
            raise DDPEConfigurationError(
                "spark.app.name is managed by the DDPE Spark Connect server "
                "and cannot be set by the client."
            )
        if not self.spark_connect_url.strip():
            raise DDPEConfigurationError("spark_connect_url cannot be empty.")
        if not self.access_token:
            missing = [
                name
                for name, value in {
                    "token_url": self.token_url,
                    "client_id": self.client_id,
                    "username": self.username,
                    "password": self.password,
                }.items()
                if not value
            ]
            if missing:
                raise DDPEConfigurationError(
                    "Missing Keycloak configuration: " + ", ".join(missing)
                )
        for candidate, label in (
            (self.spark_connect_ca, "spark_connect_ca"),
            (self.keycloak_ca, "keycloak_ca"),
            (self.verify_ssl if isinstance(self.verify_ssl, str) else None, "verify_ssl"),
        ):
            if candidate and not Path(candidate).is_file():
                raise DDPEConfigurationError(f"{label} file not found: {candidate}")
        if self.timeout_seconds <= 0:
            raise DDPEConfigurationError("timeout_seconds must be greater than zero.")
        if self.refresh_skew_seconds < 0:
            raise DDPEConfigurationError("refresh_skew_seconds cannot be negative.")


def load_config(
    *,
    config_file: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> DDPEConfig:
    """Resolve configuration using builder > environment > TOML > defaults."""

    env = os.environ if environ is None else environ
    explicit_path = config_file or env.get("DDPE_CONFIG_FILE")
    path = Path(explicit_path).expanduser() if explicit_path else DEFAULT_CONFIG_FILE
    file_values = _read_toml(path, required=bool(explicit_path))
    spark_config = {
        str(key): str(value) for key, value in dict(file_values.pop("spark_config", {})).items()
    }

    values = dict(_DEFAULTS)
    for key in _DEFAULTS:
        if key in file_values:
            values[key] = file_values[key]
        env_name = _ENV[key]
        if env_name in env:
            values[key] = env[env_name]

    override_values = dict(overrides or {})
    override_spark = override_values.pop("spark_config", {})
    values.update({key: value for key, value in override_values.items() if value is not None})
    spark_config.update({str(key): str(value) for key, value in dict(override_spark).items()})

    spark_connect_url = values.get("spark_connect_url")
    if spark_connect_url is None or not str(spark_connect_url).strip():
        raise DDPEConfigurationError(
            "Missing required Spark Connect URL. Set DDPE_SPARK_CONNECT_URL, "
            "configure ddpe.spark_connect_url in TOML, or call "
            "DDPESession.builder.remote(...)."
        )

    try:
        config = DDPEConfig(
            spark_connect_url=str(spark_connect_url),
            spark_connect_ca=(
                str(Path(str(values["spark_connect_ca"])).expanduser())
                if values["spark_connect_ca"]
                else None
            ),
            token_url=str(values["token_url"]),
            client_id=str(values["client_id"]),
            client_secret=str(values["client_secret"]),
            username=str(values["username"]),
            password=str(values["password"]),
            scope=str(values["scope"]),
            keycloak_ca=(
                str(Path(str(values["keycloak_ca"])).expanduser())
                if values["keycloak_ca"]
                else None
            ),
            verify_ssl=_parse_verify_ssl(values["verify_ssl"]),
            timeout_seconds=float(values["timeout_seconds"]),
            refresh_skew_seconds=int(values["refresh_skew_seconds"]),
            access_token=str(values["access_token"]) if values["access_token"] else None,
            spark_config=spark_config,
        )
    except (TypeError, ValueError) as exc:
        raise DDPEConfigurationError(f"Invalid DDPE configuration value: {exc}") from exc
    config.validate()
    return config
