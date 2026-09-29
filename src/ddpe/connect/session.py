"""Entry point for authenticated DDPE Spark sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import os

from .auth import KeycloakAuthenticator
from .config import DDPEConfig, load_config
from .errors import DDPEConfigurationError, DDPEConnectionError, DDPEDependencyError


def _normalize_remote(value: str) -> str:
    remote = value.strip()
    if remote.startswith("sc://"):
        remote = remote[5:]
    remote = remote.rstrip("/")
    if not remote:
        raise DDPEConfigurationError("spark_connect_url cannot be empty.")
    if "/" in remote or ";" in remote or "?" in remote:
        raise DDPEConfigurationError(
            "spark_connect_url must contain only host[:port], without a path or parameters."
        )
    return remote


def _redact(message: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")
    return message


class DDPEBuilder:
    """Fluent builder for a DDPE-backed ``pyspark.sql.SparkSession``."""

    def __init__(self) -> None:
        self._config_file: str | Path | None = None
        self._overrides: dict[str, Any] = {}
        self._spark_config: dict[str, str] = {}
        self._force_refresh = False

    def config_file(self, path: str | Path) -> DDPEBuilder:
        self._config_file = path
        return self

    def remote(self, url: str) -> DDPEBuilder:
        self._overrides["spark_connect_url"] = url
        return self

    def token_url(self, url: str) -> DDPEBuilder:
        self._overrides["token_url"] = url
        return self

    def credentials(
        self,
        *,
        username: str,
        password: str,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> DDPEBuilder:
        self._overrides.update({"username": username, "password": password})
        if client_id is not None:
            self._overrides["client_id"] = client_id
        if client_secret is not None:
            self._overrides["client_secret"] = client_secret
        return self

    def access_token(self, token: str) -> DDPEBuilder:
        self._overrides["access_token"] = token
        return self

    def verify_keycloak_ssl(self, enabled: bool = True) -> DDPEBuilder:
        """Enable or disable TLS certificate verification for Keycloak HTTPS."""

        self._overrides["verify_ssl"] = enabled
        return self

    def keycloak_ca_cert(self, path: str | Path) -> DDPEBuilder:
        """Set the PEM CA bundle used only for the Keycloak HTTPS endpoint."""

        self._overrides["keycloak_ca"] = str(path)
        return self

    def spark_ca_cert(self, path: str | Path) -> DDPEBuilder:
        """Set the PEM CA bundle used only by the Spark Connect gRPC channel."""

        self._overrides["spark_connect_ca"] = str(path)
        return self

    def verify_ssl(self, value: bool | str = True) -> DDPEBuilder:
        """Compatibility alias for Keycloak verification configuration."""

        if isinstance(value, bool):
            return self.verify_keycloak_ssl(value)
        return self.keycloak_ca_cert(value)

    def ca_cert(self, path: str | Path) -> DDPEBuilder:
        """Compatibility alias for :meth:`spark_ca_cert`."""

        return self.spark_ca_cert(path)

    def config(self, key: str, value: Any) -> DDPEBuilder:
        normalized_key = str(key)
        if normalized_key == "spark.app.name":
            raise DDPEConfigurationError(
                "spark.app.name is managed by the DDPE Spark Connect server "
                "and cannot be set by the client."
            )
        self._spark_config[normalized_key] = str(value)
        return self

    def configs(self, values: Mapping[str, Any]) -> DDPEBuilder:
        for key, value in values.items():
            self.config(key, value)
        return self

    def force_token_refresh(self, enabled: bool = True) -> DDPEBuilder:
        self._force_refresh = enabled
        return self

    def _load(self) -> DDPEConfig:
        return load_config(
            config_file=self._config_file,
            overrides={**self._overrides, "spark_config": self._spark_config},
        )

    def getOrCreate(self):  # noqa: N802 - mirrors PySpark
        config = self._load()
        if config.spark_connect_ca:
            os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = config.spark_connect_ca

        token = KeycloakAuthenticator(config).get_token(force_refresh=self._force_refresh)
        remote = f"sc://{_normalize_remote(config.spark_connect_url)}/;token={token}"

        try:
            from pyspark.sql import SparkSession
        except ImportError as exc:
            raise DDPEDependencyError(
                "PySpark Connect is not installed. Reinstall from GitHub with: "
                '\'pip install "git+https://github.com/JFG-UOC/ddpe-connect.git@main"\''
            ) from exc

        try:
            builder = SparkSession.builder.remote(remote)
            for key, value in config.spark_config.items():
                builder = builder.config(key, value)
            return builder.getOrCreate()
        except Exception as exc:
            cause = _redact(str(exc), token, config.password, config.client_secret)
            raise DDPEConnectionError(
                f"Unable to create the DDPE Spark Connect session for "
                f"{config.spark_connect_url!r}: {cause}"
            ) from exc


class _BuilderDescriptor:
    def __get__(self, instance: object, owner: type) -> DDPEBuilder:
        return DDPEBuilder()


class DDPESession:
    """Public entry point for building authenticated DDPE sessions."""

    builder = _BuilderDescriptor()
