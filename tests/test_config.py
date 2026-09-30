from __future__ import annotations

import pytest

from ddpe.connect.config import load_config
from ddpe.connect.errors import DDPEConfigurationError


def _env(**updates):
    values = {
        "DDPE_SPARK_CONNECT_URL": "spark.example:443",
        "DDPE_USERNAME": "user",
        "DDPE_PASSWORD": "password",
    }
    values.update(updates)
    return values


def test_defaults_are_available_when_required_url_is_provided():
    config = load_config(environ=_env())
    assert config.spark_connect_url == "spark.example:443"
    assert config.client_id == "ddpe-client"
    assert config.verify_ssl is True


def test_spark_connect_url_is_required():
    with pytest.raises(DDPEConfigurationError, match="Missing required Spark Connect URL"):
        load_config(
            environ={
                "DDPE_USERNAME": "user",
                "DDPE_PASSWORD": "password",
            }
        )


def test_empty_spark_connect_url_is_rejected():
    with pytest.raises(DDPEConfigurationError, match="Missing required Spark Connect URL"):
        load_config(environ=_env(DDPE_SPARK_CONNECT_URL="  "))


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


def test_builder_can_supply_required_url_without_environment_value():
    config = load_config(
        environ={
            "DDPE_USERNAME": "user",
            "DDPE_PASSWORD": "password",
        },
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
[ddpe]
spark_connect_url = "spark.example:443"
access_token = "token"

[ddpe.spark]
"spark.app.name" = "client-name"
''',
        encoding="utf-8",
    )
    with pytest.raises(DDPEConfigurationError, match="managed by the DDPE"):
        load_config(config_file=path, environ={})


def test_access_token_does_not_require_password_credentials():
    config = load_config(
        environ={
            "DDPE_SPARK_CONNECT_URL": "spark.example:443",
            "DDPE_ACCESS_TOKEN": "token",
        }
    )
    assert config.access_token == "token"


def test_spark_and_keycloak_ca_paths_are_independent(tmp_path):
    spark_ca = tmp_path / "spark-ca.pem"
    keycloak_ca = tmp_path / "keycloak-ca.pem"
    spark_ca.write_text("spark-ca", encoding="utf-8")
    keycloak_ca.write_text("keycloak-ca", encoding="utf-8")

    config = load_config(
        environ=_env(
            DDPE_SPARK_CONNECT_CA=str(spark_ca),
            DDPE_KEYCLOAK_CA=str(keycloak_ca),
        )
    )

    assert config.spark_connect_ca == str(spark_ca)
    assert config.keycloak_ca == str(keycloak_ca)
    assert config.spark_connect_ca != config.keycloak_ca


@pytest.mark.parametrize("setting", ["verify_ssl", "spark_verify_ssl"])
def test_toml_rejects_attempt_to_disable_spark_tls_verification(tmp_path, setting):
    path = tmp_path / "config.toml"
    path.write_text(
        f'''
[ddpe]
spark_connect_url = "spark.example:443"
access_token = "token"
{setting} = false
''',
        encoding="utf-8",
    )
    with pytest.raises(DDPEConfigurationError, match="cannot disable Spark Connect TLS"):
        load_config(config_file=path, environ={})
