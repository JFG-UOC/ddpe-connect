"""Builder-based configuration for notebooks and short-lived scripts."""

import os

from ddpe.connect import DDPESession

# The DDPE Spark Connect server owns the application name.
spark = (
    DDPESession.builder
    .remote("spark-connect.example:443")
    .token_url("https://keycloak.example/auth/realms/ddae/protocol/openid-connect/token")
    .credentials(
        username=os.environ["DDPE_USERNAME"],
        password=os.environ["DDPE_PASSWORD"],
        client_id="ddpe-client",
        client_secret=os.environ.get("DDPE_OIDC_CLIENT_SECRET", ""),
    )
    .spark_ca_cert("/path/to/spark-connect-ca.pem")
    .keycloak_ca_cert("/path/to/keycloak-ca.pem")
    .config("spark.sql.shuffle.partitions", "16")
    .getOrCreate()
)
