from __future__ import annotations

import pytest

from ddpe.connect.config import load_config
from ddpe.connect.errors import DDPEConfigurationError


def _env(**updates):
    values = {
        "DDPE_USERNAME": "user",
        "DDPE_PASSWORD": "password",
    }
    values.update(updates)
    return values


def test_defaults_are_available_without_a_file():
    config = load_config(environ=_env())
    assert config.spark_connect_url == "localhost:15002"
    assert config.client_id == "ddpe-client"
    assert config.verify_ssl is True


def test_environment_overrides_defaults():
    config = load_config(
        environ=_env(
            DDPE_SPARK_CONNECT_URL="spark.example:443",
            DDPE_VERIFY_SSL="false",
            DDPE_AUTH_TIMEOUT_SECONDS="12.5",
        )
    )
    assert config.spark_connect_url == "spark.example:443"
    assert config.verify_ssl is False
    assert config.timeout_seconds == 12.5


def test_builder_overrides_environment():
    config = load_config(
        environ=_env(DDPE_SPARK_CONNECT_URL="env.example"),
        overrides={"spark_connect_url": "builder.example"},
    )
    assert config.spark_connect_url == "builder.example"


def test_toml_loads_auth_and_spark_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[ddpe]
spark_connect_url = "spark.example:443"

[ddpe.auth]
token_url = "https://keycloak.example/token"
client_id = "client"
username = "toml-user"
password = "toml-pass"
verify_ssl = true

[ddpe.spark]
"spark.sql.shuffle.partitions" = 8
""",
        encoding="utf-8",
    )
    config = load_config(config_file=path, environ={})
    assert config.username == "toml-user"
    assert config.spark_config == {"spark.sql.shuffle.partitions": "8"}


def test_missing_explicit_file_fails(tmp_path):
    with pytest.raises(DDPEConfigurationError, match="not found"):
        load_config(config_file=tmp_path / "missing.toml", environ={})


def test_ca_path_must_exist(tmp_path):
    with pytest.raises(DDPEConfigurationError, match="file not found"):
        load_config(
            environ=_env(DDPE_SPARK_CONNECT_CA=str(tmp_path / "missing.pem"))
        )


def test_toml_rejects_application_name(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '''
[ddpe.auth]
username = "user"
password = "password"

[ddpe.spark]
"spark.app.name" = "client-name"
''',
        encoding="utf-8",
    )
    with pytest.raises(DDPEConfigurationError, match="managed by the DDPE"):
        load_config(config_file=path, environ={})


def test_access_token_does_not_require_password_credentials():
    config = load_config(environ={"DDPE_ACCESS_TOKEN": "token"})
    assert config.access_token == "token"
