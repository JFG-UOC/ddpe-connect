"""Builder-based configuration for notebooks and short-lived scripts."""

import os

from ddpe.connect import DDPESession

# The DDPE Spark Connect server owns the application name.
spark = (
    DDPESession.builder
    .remote("spark-connect.example:443")
    .token_url("https://keycloak.example/realms/ddpe/protocol/openid-connect/token")
    .credentials(
        username=os.environ["DDPE_USERNAME"],
        password=os.environ["DDPE_PASSWORD"],
        client_id="ddpe-client",
        client_secret=os.environ.get("DDPE_OIDC_CLIENT_SECRET", ""),
    )
    .ca_cert("/path/to/ddpe-ca.pem")
    .verify_ssl("/path/to/keycloak-ca.pem")
    .config("spark.sql.shuffle.partitions", "16")
    .getOrCreate()
)
