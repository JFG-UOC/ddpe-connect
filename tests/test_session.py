from __future__ import annotations

import os
import sys
import types

import pytest

from ddpe.connect import DDPESession
from ddpe.connect.errors import DDPEConfigurationError, DDPEConnectionError
from ddpe.connect.session import _normalize_remote


def test_builder_is_fresh():
    assert DDPESession.builder is not DDPESession.builder


def test_remote_normalization():
    assert _normalize_remote("sc://spark.example:443/") == "spark.example:443"


@pytest.mark.parametrize("value", ["host/path", "host;token=x", "host?x=1"])
def test_remote_rejects_embedded_parameters(value):
    with pytest.raises(DDPEConfigurationError):
        _normalize_remote(value)


def test_session_builder_constructs_authenticated_remote(monkeypatch, tmp_path):
    seen = {"configs": []}

    class FakeBuilder:
        def remote(self, value):
            seen["remote"] = value
            return self

        def config(self, key, value):
            seen["configs"].append((key, value))
            return self

        def getOrCreate(self):
            return "spark-session"

    sql = types.ModuleType("pyspark.sql")
    sql.SparkSession = types.SimpleNamespace(builder=FakeBuilder())
    pyspark = types.ModuleType("pyspark")
    pyspark.sql = sql
    monkeypatch.setitem(sys.modules, "pyspark", pyspark)
    monkeypatch.setitem(sys.modules, "pyspark.sql", sql)

    ca = tmp_path / "ca.pem"
    ca.write_text("certificate", encoding="utf-8")
    result = (
        DDPESession.builder
        .remote("spark.example:443")
        .access_token("secret-token")
        .spark_ca_cert(ca)
        .config("spark.sql.shuffle.partitions", 4)
        .getOrCreate()
    )

    assert result == "spark-session"
    assert seen["remote"] == "sc://spark.example:443/;token=secret-token"
    assert ("spark.sql.shuffle.partitions", "4") in seen["configs"]
    assert os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] == str(ca)


def test_builder_rejects_application_name():
    with pytest.raises(DDPEConfigurationError, match="managed by the DDPE"):
        DDPESession.builder.config("spark.app.name", "client-name")


def test_connection_errors_redact_secrets(monkeypatch):
    class FakeBuilder:
        def remote(self, value):
            return self

        def getOrCreate(self):
            raise RuntimeError("failure includes sensitive-token")

    sql = types.ModuleType("pyspark.sql")
    sql.SparkSession = types.SimpleNamespace(builder=FakeBuilder())
    pyspark = types.ModuleType("pyspark")
    monkeypatch.setitem(sys.modules, "pyspark", pyspark)
    monkeypatch.setitem(sys.modules, "pyspark.sql", sql)

    with pytest.raises(DDPEConnectionError) as captured:
        (
            DDPESession.builder
            .remote("spark.example:443")
            .access_token("sensitive-token")
            .getOrCreate()
        )
    assert "sensitive-token" not in str(captured.value)


def test_builder_configures_distinct_spark_and_keycloak_cas(tmp_path):
    spark_ca = tmp_path / "spark-ca.pem"
    keycloak_ca = tmp_path / "keycloak-ca.pem"
    spark_ca.write_text("spark-ca", encoding="utf-8")
    keycloak_ca.write_text("keycloak-ca", encoding="utf-8")

    config = (
        DDPESession.builder
        .remote("spark.example:443")
        .access_token("token")
        .spark_ca_cert(spark_ca)
        .keycloak_ca_cert(keycloak_ca)
        ._load()
    )

    assert config.spark_connect_ca == str(spark_ca)
    assert config.keycloak_ca == str(keycloak_ca)
